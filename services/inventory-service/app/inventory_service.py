from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .errors import DomainError
from .inventory_schemas import BatchInventoryItem, InventoryLogItem, InventorySummary, ProductCreate, ProductSaleStatusUpdate
from .legacy_sync import sync_clinic_catalog_and_paid_invoices, upsert_source_medicine
from .models import InventoryAction, InventoryLog, Prescription, PrescriptionStatus, Product, ProductBatch
from .schemas import ProductSummary


async def create_product(session: AsyncSession, payload: ProductCreate) -> ProductSummary:
    await sync_clinic_catalog_and_paid_invoices(session)
    normalized_sku = payload.sku.strip().upper()
    if await session.scalar(select(Product.id).where(func.lower(Product.sku) == normalized_sku.lower())):
        raise DomainError(409, "PRODUCT_SKU_EXISTS", "Mã SKU đã tồn tại trong danh mục thuốc.")

    product = Product(
        sku=normalized_sku,
        name=payload.name.strip(),
        unit=payload.unit.strip(),
        import_price=payload.import_price,
        selling_price=payload.selling_price,
        min_threshold=payload.min_threshold,
    )
    session.add(product)
    await session.flush()
    await upsert_source_medicine(
        session,
        product_id=product.id,
        sku=product.sku,
        name=product.name,
        unit=product.unit,
        selling_price=product.selling_price,
    )
    await session.commit()
    await session.refresh(product)
    return ProductSummary(
        id=product.id,
        sku=product.sku,
        name=product.name,
        unit=product.unit,
        import_price=product.import_price,
        selling_price=product.selling_price,
        min_threshold=product.min_threshold,
        active=product.active,
        current_quantity=0,
    )


async def set_product_sale_status(
    session: AsyncSession,
    product_id: object,
    payload: ProductSaleStatusUpdate,
) -> ProductSummary:
    await sync_clinic_catalog_and_paid_invoices(session)
    async with session.begin():
        product = await session.scalar(select(Product).where(Product.id == product_id).with_for_update())
        if not product:
            raise DomainError(404, "PRODUCT_NOT_FOUND", "Không tìm thấy thuốc trong danh mục.")
        product.active = payload.active
        source = await session.execute(text("""
            UPDATE prescription.medicines
            SET active = :active,
                updated_at = CURRENT_TIMESTAMP,
                version = version + 1
            WHERE id = :product_id
        """), {"active": payload.active, "product_id": product.id})
        if source.rowcount == 0:
            raise DomainError(409, "SOURCE_MEDICINE_NOT_FOUND", "Không tìm thấy thuốc trong danh mục kê đơn.")

    today = date.today()
    quantity = int(await session.scalar(
        select(func.coalesce(func.sum(ProductBatch.quantity), 0)).where(
            ProductBatch.product_id == product.id,
            ProductBatch.expiry_date >= today,
        )
    ) or 0)
    return ProductSummary(
        id=product.id,
        sku=product.sku,
        name=product.name,
        unit=product.unit,
        import_price=product.import_price,
        selling_price=product.selling_price,
        min_threshold=product.min_threshold,
        active=product.active,
        current_quantity=quantity,
    )


async def list_batches(session: AsyncSession) -> list[BatchInventoryItem]:
    today = date.today()
    rows = (await session.execute(
        select(ProductBatch, Product)
        .join(Product, Product.id == ProductBatch.product_id)
        .order_by(Product.name, ProductBatch.expiry_date, ProductBatch.batch_number)
    )).all()
    result: list[BatchInventoryItem] = []
    for batch, product in rows:
        days_remaining = (batch.expiry_date - today).days
        status = "EXPIRED" if days_remaining < 0 else "EXPIRING" if days_remaining <= 30 else "ACTIVE"
        if batch.quantity == 0:
            status = "OUT_OF_STOCK"
        result.append(BatchInventoryItem(
            id=batch.id,
            product_id=product.id,
            sku=product.sku,
            product_name=product.name,
            unit=product.unit,
            batch_number=batch.batch_number,
            expiry_date=batch.expiry_date,
            quantity=batch.quantity,
            days_remaining=days_remaining,
            status=status,
        ))
    return result


async def list_inventory_logs(
    session: AsyncSession,
    limit: int,
    action_type: InventoryAction | None,
    search: str | None,
) -> list[InventoryLogItem]:
    statement = (
        select(InventoryLog, Product, ProductBatch)
        .join(Product, Product.id == InventoryLog.product_id)
        .join(ProductBatch, ProductBatch.id == InventoryLog.batch_id)
        .order_by(InventoryLog.created_at.desc(), InventoryLog.id.desc())
        .limit(limit)
    )
    if action_type:
        statement = statement.where(InventoryLog.action_type == action_type)
    if search and (term := search.strip()):
        pattern = f"%{term}%"
        statement = statement.where(or_(
            Product.name.ilike(pattern),
            Product.sku.ilike(pattern),
            ProductBatch.batch_number.ilike(pattern),
        ))
    rows = (await session.execute(statement)).all()
    return [InventoryLogItem(
        id=log.id,
        product_id=product.id,
        batch_id=batch.id,
        sku=product.sku,
        product_name=product.name,
        unit=product.unit,
        batch_number=batch.batch_number,
        action_type=log.action_type,
        quantity_changed=log.quantity_changed,
        created_at=log.created_at,
    ) for log, product, batch in rows]


async def inventory_summary(session: AsyncSession) -> InventorySummary:
    today = date.today()
    deadline = today + timedelta(days=30)
    start_of_day = datetime.combine(today, time.min, tzinfo=timezone.utc)
    stock_by_product = (
        select(
            Product.id.label("product_id"),
            func.coalesce(func.sum(ProductBatch.quantity).filter(ProductBatch.expiry_date >= today), 0).label("stock"),
        )
        .outerjoin(ProductBatch, ProductBatch.product_id == Product.id)
        .group_by(Product.id)
        .subquery()
    )

    product_count = int(await session.scalar(select(func.count(Product.id))) or 0)
    active_batch_count = int(await session.scalar(select(func.count(ProductBatch.id)).where(ProductBatch.quantity > 0, ProductBatch.expiry_date >= today)) or 0)
    available_quantity = int(await session.scalar(select(func.coalesce(func.sum(ProductBatch.quantity), 0)).where(ProductBatch.expiry_date >= today)) or 0)
    pending_count = int(await session.scalar(select(func.count(Prescription.id)).where(Prescription.status == PrescriptionStatus.PAID)) or 0)
    low_stock_count = int(await session.scalar(
        select(func.count()).select_from(Product).join(stock_by_product, stock_by_product.c.product_id == Product.id).where(stock_by_product.c.stock < Product.min_threshold)
    ) or 0)
    expiring_count = int(await session.scalar(select(func.count(ProductBatch.id)).where(ProductBatch.quantity > 0, ProductBatch.expiry_date.between(today, deadline))) or 0)
    imports_today = int(await session.scalar(select(func.coalesce(func.sum(InventoryLog.quantity_changed), 0)).where(InventoryLog.action_type == InventoryAction.IMPORT, InventoryLog.created_at >= start_of_day)) or 0)
    dispensed_today = abs(int(await session.scalar(select(func.coalesce(func.sum(InventoryLog.quantity_changed), 0)).where(InventoryLog.action_type == InventoryAction.DISPENSE, InventoryLog.created_at >= start_of_day)) or 0))

    return InventorySummary(
        product_count=product_count,
        active_batch_count=active_batch_count,
        available_quantity=available_quantity,
        pending_prescription_count=pending_count,
        low_stock_count=low_stock_count,
        expiring_batch_count=expiring_count,
        imports_today=imports_today,
        dispensed_today=dispensed_today,
    )
