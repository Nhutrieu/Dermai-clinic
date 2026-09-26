from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .errors import DomainError
from .legacy_sync import (
    mark_source_invoice_dispensed,
    refresh_source_medicine_stock,
    sync_clinic_catalog_and_paid_invoices,
)
from .models import InventoryAction, InventoryLog, Prescription, PrescriptionItem, PrescriptionStatus, Product, ProductBatch
from .schemas import (
    BatchOption,
    BatchResponse,
    DispenseRequest,
    DispenseResponse,
    ExpiringBatchAlert,
    ImportBatchRequest,
    LowStockAlert,
    PendingItem,
    PendingPrescription,
    ProductSummary,
)


def eligible_batches(batches: list[ProductBatch], required_quantity: int, today: date | None = None) -> list[ProductBatch]:
    current_date = today or date.today()
    return sorted(
        (batch for batch in batches if batch.quantity > 0 and batch.expiry_date >= current_date),
        key=lambda batch: (batch.expiry_date, batch.batch_number, str(batch.id)),
    )


async def list_products(session: AsyncSession) -> list[ProductSummary]:
    await sync_clinic_catalog_and_paid_invoices(session)
    today = date.today()
    stock = func.coalesce(func.sum(ProductBatch.quantity).filter(ProductBatch.expiry_date >= today), 0)
    rows = (await session.execute(
        select(Product, stock.label("current_quantity"))
        .outerjoin(ProductBatch, ProductBatch.product_id == Product.id)
        .group_by(Product.id)
        .order_by(Product.name)
    )).all()
    return [ProductSummary(
        id=product.id,
        sku=product.sku,
        name=product.name,
        unit=product.unit,
        import_price=product.import_price,
        selling_price=product.selling_price,
        min_threshold=product.min_threshold,
        active=product.active,
        current_quantity=int(quantity),
    ) for product, quantity in rows]


async def list_pending_prescriptions(session: AsyncSession) -> list[PendingPrescription]:
    await sync_clinic_catalog_and_paid_invoices(session)
    prescriptions = (await session.scalars(
        select(Prescription)
        .where(Prescription.status == PrescriptionStatus.PAID)
        .options(selectinload(Prescription.items).selectinload(PrescriptionItem.product).selectinload(Product.batches))
        .order_by(Prescription.paid_at.asc(), Prescription.id.asc())
    )).unique().all()

    result: list[PendingPrescription] = []
    for prescription in prescriptions:
        items: list[PendingItem] = []
        for item in prescription.items:
            batches = eligible_batches(item.product.batches, item.quantity)
            recommended = next((batch for batch in batches if batch.quantity >= item.quantity), None)
            items.append(PendingItem(
                id=item.id,
                product_id=item.product_id,
                sku=item.product.sku,
                product_name=item.product.name,
                unit=item.product.unit,
                quantity=item.quantity,
                recommended_batch_id=recommended.id if recommended else None,
                available_batches=[BatchOption(
                    id=batch.id,
                    batch_number=batch.batch_number,
                    expiry_date=batch.expiry_date,
                    quantity=batch.quantity,
                    is_fefo=batch.id == (recommended.id if recommended else None),
                ) for batch in batches],
            ))
        result.append(PendingPrescription(
            id=prescription.id,
            code=f"RX-{str(prescription.id)[:8].upper()}",
            patient_id=prescription.patient_id,
            patient_name=prescription.patient_name,
            doctor_id=prescription.doctor_id,
            status=prescription.status,
            paid_at=prescription.paid_at or datetime.now(timezone.utc),
            items=items,
        ))
    return result


async def dispense_prescription(
    session: AsyncSession,
    payload: DispenseRequest,
    pharmacist_id: uuid.UUID,
) -> DispenseResponse:
    async with session.begin():
        prescription = await session.scalar(
            select(Prescription).where(Prescription.id == payload.prescription_id).with_for_update()
        )
        if not prescription:
            raise DomainError(404, "PRESCRIPTION_NOT_FOUND", "Không tìm thấy đơn thuốc cần xuất.")
        if prescription.status != PrescriptionStatus.PAID:
            raise DomainError(409, "PRESCRIPTION_NOT_PAID", "Đơn thuốc không còn ở trạng thái chờ xuất kho.")

        items = (await session.scalars(
            select(PrescriptionItem).where(PrescriptionItem.prescription_id == prescription.id)
        )).all()
        item_by_id = {item.id: item for item in items}
        requested_by_item = {item.item_id: item.batch_id for item in payload.items}
        if len(requested_by_item) != len(payload.items) or set(requested_by_item) != set(item_by_id):
            raise DomainError(422, "INVALID_DISPENSE_ITEMS", "Cần chọn đúng một lô cho từng thuốc trong đơn.")

        batch_ids = sorted(set(requested_by_item.values()), key=str)
        locked_batches = (await session.scalars(
            select(ProductBatch).where(ProductBatch.id.in_(batch_ids)).order_by(ProductBatch.id).with_for_update()
        )).all()
        batch_by_id = {batch.id: batch for batch in locked_batches}
        if set(batch_by_id) != set(batch_ids):
            raise DomainError(409, "BATCH_NOT_AVAILABLE", "Một lô thuốc vừa được thay đổi hoặc không còn tồn tại.")

        today = date.today()
        required_by_batch: dict[uuid.UUID, int] = {}
        for item_id, batch_id in requested_by_item.items():
            item = item_by_id[item_id]
            batch = batch_by_id[batch_id]
            if batch.product_id != item.product_id or batch.expiry_date < today:
                raise DomainError(409, "BATCH_NOT_AVAILABLE", "Lô đã chọn không hợp lệ hoặc đã hết hạn.")
            required_by_batch[batch_id] = required_by_batch.get(batch_id, 0) + item.quantity

        for batch_id, required_quantity in required_by_batch.items():
            batch = batch_by_id[batch_id]
            if batch.quantity < required_quantity:
                raise DomainError(
                    409,
                    "INSUFFICIENT_STOCK",
                    f"Lô {batch.batch_number} chỉ còn {batch.quantity}, không đủ {required_quantity} đơn vị.",
                )

        for item_id, batch_id in requested_by_item.items():
            item = item_by_id[item_id]
            batch = batch_by_id[batch_id]
            batch.quantity -= item.quantity
            item.batch_id = batch.id
            session.add(InventoryLog(
                product_id=item.product_id,
                batch_id=batch.id,
                action_type=InventoryAction.DISPENSE,
                quantity_changed=-item.quantity,
            ))

        dispensed_at = datetime.now(timezone.utc)
        prescription.status = PrescriptionStatus.DISPENSED
        prescription.dispensed_at = dispensed_at
        prescription.dispensed_by = pharmacist_id
        await session.flush()
        for product_id in sorted({item.product_id for item in items}, key=str):
            await refresh_source_medicine_stock(session, product_id)
        await mark_source_invoice_dispensed(session, prescription.id, pharmacist_id, dispensed_at)

    return DispenseResponse(
        prescription_id=prescription.id,
        status=prescription.status,
        dispensed_at=dispensed_at,
    )


async def import_batch(session: AsyncSession, payload: ImportBatchRequest) -> BatchResponse:
    if payload.expiry_date <= date.today():
        raise DomainError(422, "INVALID_EXPIRY_DATE", "Hạn sử dụng phải sau ngày hiện tại.")
    normalized_number = payload.batch_number.strip().upper()

    async with session.begin():
        product = await session.scalar(select(Product).where(Product.id == payload.product_id).with_for_update())
        if not product:
            raise DomainError(404, "PRODUCT_NOT_FOUND", "Không tìm thấy thuốc trong danh mục.")
        if not product.active:
            raise DomainError(409, "PRODUCT_INACTIVE", "Thuốc đang ngưng bán nên không thể nhập lô mới.")

        batch = await session.scalar(
            select(ProductBatch)
            .where(and_(ProductBatch.product_id == product.id, ProductBatch.batch_number == normalized_number))
            .with_for_update()
        )
        if batch:
            if batch.expiry_date != payload.expiry_date:
                raise DomainError(409, "BATCH_EXPIRY_MISMATCH", "Số lô đã tồn tại với hạn sử dụng khác.")
            batch.quantity += payload.quantity
        else:
            batch = ProductBatch(
                product_id=product.id,
                batch_number=normalized_number,
                expiry_date=payload.expiry_date,
                quantity=payload.quantity,
            )
            session.add(batch)
            await session.flush()

        session.add(InventoryLog(
            product_id=product.id,
            batch_id=batch.id,
            action_type=InventoryAction.IMPORT,
            quantity_changed=payload.quantity,
        ))
        await session.flush()
        await refresh_source_medicine_stock(session, product.id)

    return BatchResponse.model_validate(batch)


async def low_stock_alerts(session: AsyncSession) -> list[LowStockAlert]:
    today = date.today()
    stock = func.coalesce(func.sum(ProductBatch.quantity).filter(ProductBatch.expiry_date >= today), 0)
    rows = (await session.execute(
        select(Product, stock.label("current_quantity"))
        .outerjoin(ProductBatch, ProductBatch.product_id == Product.id)
        .group_by(Product.id)
        .having(stock < Product.min_threshold)
        .order_by((Product.min_threshold - stock).desc(), Product.name)
    )).all()
    return [LowStockAlert(
        product_id=product.id,
        sku=product.sku,
        name=product.name,
        unit=product.unit,
        current_quantity=int(quantity),
        min_threshold=product.min_threshold,
        shortage_quantity=product.min_threshold - int(quantity),
    ) for product, quantity in rows]


async def expiring_batch_alerts(session: AsyncSession) -> list[ExpiringBatchAlert]:
    today = date.today()
    deadline = today + timedelta(days=30)
    rows = (await session.execute(
        select(ProductBatch, Product)
        .join(Product, Product.id == ProductBatch.product_id)
        .where(
            ProductBatch.expiry_date.between(today, deadline),
            ProductBatch.quantity > 0,
        )
        .order_by(ProductBatch.expiry_date, Product.name)
    )).all()
    return [ExpiringBatchAlert(
        batch_id=batch.id,
        product_id=product.id,
        sku=product.sku,
        product_name=product.name,
        batch_number=batch.batch_number,
        expiry_date=batch.expiry_date,
        quantity=batch.quantity,
        days_remaining=(batch.expiry_date - today).days,
    ) for batch, product in rows]
