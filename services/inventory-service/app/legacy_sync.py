from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def sync_clinic_catalog_and_paid_invoices(session: AsyncSession) -> None:
    """Import operational data owned by the existing prescription service.

    DermAI currently keeps billing data in the same PostgreSQL database under
    the ``prescription`` schema.  This bridge is idempotent: it mirrors the
    real medicine catalogue and newly paid invoices into the pharmacy schema,
    while preserving prices and thresholds maintained by pharmacists.
    """
    medicines_table = await session.scalar(text("SELECT to_regclass('prescription.medicines')"))
    invoices_table = await session.scalar(text("SELECT to_regclass('prescription.invoices')"))
    patients_table = await session.scalar(text("SELECT to_regclass('patient.patients')"))
    if not medicines_table:
        return

    await session.execute(text("""
        INSERT INTO pharmacy.products (
            id, sku, name, unit, import_price, selling_price, min_threshold, active
        )
        SELECT id, sku, name, unit, 0, sale_price, 0, TRUE
        FROM prescription.medicines
        WHERE active = TRUE
        ON CONFLICT (id) DO UPDATE SET
            sku = EXCLUDED.sku,
            name = EXCLUDED.name,
            unit = EXCLUDED.unit,
            selling_price = EXCLUDED.selling_price,
            active = TRUE
    """))

    await session.execute(text("""
        UPDATE pharmacy.products AS product
        SET active = medicine.active
        FROM prescription.medicines AS medicine
        WHERE product.id = medicine.id
          AND product.active IS DISTINCT FROM medicine.active
    """))

    if not invoices_table or not patients_table:
        await session.commit()
        return

    await session.execute(text("""
        INSERT INTO pharmacy.prescriptions (
            id, patient_id, patient_name, doctor_id, status, paid_at,
            dispensed_at, dispensed_by
        )
        SELECT
            invoice.id,
            invoice.patient_id,
            COALESCE(NULLIF(patient.full_name, ''), invoice.patient_id::text),
            prescription.doctor_id,
            'PAID',
            COALESCE(invoice.paid_at, invoice.created_at),
            NULL,
            NULL
        FROM prescription.invoices AS invoice
        JOIN prescription.prescriptions AS prescription
          ON prescription.id = invoice.prescription_id
        LEFT JOIN patient.patients AS patient
          ON patient.id = invoice.patient_id
        WHERE invoice.status = 'PAID'
          AND invoice.medicine_fulfillment = 'CLINIC_PHARMACY'
          AND prescription.doctor_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM prescription.invoice_items AS item
              WHERE item.invoice_id = invoice.id
                AND item.prescribed_quantity > 0
          )
        ON CONFLICT (id) DO NOTHING
    """))

    await session.execute(text("""
        INSERT INTO pharmacy.prescription_items (
            id, prescription_id, product_id, batch_id, quantity
        )
        SELECT
            md5(item.invoice_id::text || ':' || item.medicine_id::text)::uuid,
            item.invoice_id,
            item.medicine_id,
            NULL,
            SUM(item.prescribed_quantity)::integer
        FROM prescription.invoice_items AS item
        JOIN pharmacy.prescriptions AS pharmacy_prescription
          ON pharmacy_prescription.id = item.invoice_id
        JOIN pharmacy.products AS product
          ON product.id = item.medicine_id
        WHERE pharmacy_prescription.status = 'PAID'
        GROUP BY item.invoice_id, item.medicine_id
        ON CONFLICT (id) DO UPDATE SET
            quantity = EXCLUDED.quantity
    """))

    await session.execute(text("""
        UPDATE pharmacy.prescriptions AS pharmacy_prescription
        SET status = invoice.status,
            dispensed_at = invoice.dispensed_at,
            dispensed_by = invoice.dispensed_by
        FROM prescription.invoices AS invoice
        WHERE pharmacy_prescription.id = invoice.id
          AND pharmacy_prescription.status = 'PAID'
          AND invoice.status IN ('CANCELLED', 'DISPENSED')
    """))
    await session.commit()


async def upsert_source_medicine(
    session: AsyncSession,
    *,
    product_id: object,
    sku: str,
    name: str,
    unit: str,
    selling_price: object,
) -> None:
    """Publish a pharmacy product to the catalogue used by doctors."""
    medicines_table = await session.scalar(text("SELECT to_regclass('prescription.medicines')"))
    if not medicines_table:
        return
    await session.execute(text("""
        INSERT INTO prescription.medicines (
            id, sku, name, unit, sale_price, stock_quantity, active,
            updated_at, version
        ) VALUES (
            :product_id, :sku, :name, :unit, :selling_price, 0, TRUE,
            CURRENT_TIMESTAMP, 0
        )
        ON CONFLICT (id) DO UPDATE SET
            sku = EXCLUDED.sku,
            name = EXCLUDED.name,
            unit = EXCLUDED.unit,
            sale_price = EXCLUDED.sale_price,
            active = TRUE,
            updated_at = CURRENT_TIMESTAMP,
            version = prescription.medicines.version + 1
    """), {
        "product_id": product_id,
        "sku": sku,
        "name": name,
        "unit": unit,
        "selling_price": selling_price,
    })


async def refresh_source_medicine_stock(session: AsyncSession, product_id: object) -> None:
    """Expose current non-expired batch stock to the prescribing catalogue."""
    medicines_table = await session.scalar(text("SELECT to_regclass('prescription.medicines')"))
    if not medicines_table:
        return
    await session.execute(text("""
        UPDATE prescription.medicines AS medicine
        SET stock_quantity = COALESCE((
                SELECT SUM(batch.quantity)
                FROM pharmacy.product_batches AS batch
                WHERE batch.product_id = :product_id
                  AND batch.expiry_date >= CURRENT_DATE
            ), 0),
            updated_at = CURRENT_TIMESTAMP,
            version = medicine.version + 1
        WHERE medicine.id = :product_id
    """), {"product_id": product_id})

async def mark_source_invoice_dispensed(
    session: AsyncSession,
    prescription_id: object,
    pharmacist_id: object,
    dispensed_at: object,
) -> None:
    """Keep the billing UI consistent after the pharmacy transaction commits."""
    invoices_table = await session.scalar(text("SELECT to_regclass('prescription.invoices')"))
    if not invoices_table:
        return
    await session.execute(text("""
        UPDATE prescription.invoices
        SET status = 'DISPENSED',
            dispensed_at = :dispensed_at,
            dispensed_by = :pharmacist_id,
            version = version + 1
        WHERE id = :prescription_id
          AND status = 'PAID'
    """), {
        "prescription_id": prescription_id,
        "pharmacist_id": pharmacist_id,
        "dispensed_at": dispensed_at,
    })
    await session.execute(text("""
        UPDATE prescription.invoice_items
        SET dispensed_quantity = prescribed_quantity
        WHERE invoice_id = :prescription_id
    """), {"prescription_id": prescription_id})
