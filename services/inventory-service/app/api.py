import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_session
from .dependencies import PharmacistIdentity, require_inventory_viewer, require_pharmacist
from .inventory_schemas import BatchInventoryItem, InventoryLogItem, InventorySummary, ProductCreate, ProductSaleStatusUpdate
from .inventory_service import create_product, inventory_summary, list_batches, list_inventory_logs, set_product_sale_status
from .models import InventoryAction
from .schemas import BatchResponse, DispenseRequest, DispenseResponse, ExpiringBatchAlert, ImportBatchRequest, LowStockAlert, PendingPrescription, ProductSummary
from .service import dispense_prescription, expiring_batch_alerts, import_batch, list_pending_prescriptions, list_products, low_stock_alerts


Session = Annotated[AsyncSession, Depends(get_session)]
Pharmacist = Annotated[PharmacistIdentity, Depends(require_pharmacist)]
InventoryViewer = Annotated[PharmacistIdentity, Depends(require_inventory_viewer)]

router = APIRouter(prefix="/api/v1", tags=["pharmacy"])


@router.get("/pharmacy/pending-prescriptions", response_model=list[PendingPrescription])
async def pending_prescriptions(session: Session, _: Pharmacist) -> list[PendingPrescription]:
    return await list_pending_prescriptions(session)


@router.post("/pharmacy/dispense", response_model=DispenseResponse)
async def dispense(payload: DispenseRequest, session: Session, pharmacist: Pharmacist) -> DispenseResponse:
    return await dispense_prescription(session, payload, pharmacist.user_id)


@router.get("/inventory/products", response_model=list[ProductSummary])
async def products(session: Session, _: InventoryViewer) -> list[ProductSummary]:
    return await list_products(session)


@router.post("/inventory/products", response_model=ProductSummary, status_code=status.HTTP_201_CREATED)
async def add_product(payload: ProductCreate, session: Session, _: Pharmacist) -> ProductSummary:
    return await create_product(session, payload)


@router.patch("/inventory/products/{product_id}/sale-status", response_model=ProductSummary)
async def update_sale_status(
    product_id: uuid.UUID,
    payload: ProductSaleStatusUpdate,
    session: Session,
    _: Pharmacist,
) -> ProductSummary:
    return await set_product_sale_status(session, product_id, payload)


@router.get("/inventory/batches", response_model=list[BatchInventoryItem])
async def batches(session: Session, _: InventoryViewer) -> list[BatchInventoryItem]:
    return await list_batches(session)


@router.get("/inventory/logs", response_model=list[InventoryLogItem])
async def logs(
    session: Session,
    _: InventoryViewer,
    limit: int = Query(default=100, ge=1, le=500),
    action_type: InventoryAction | None = Query(default=None, alias="actionType"),
    search: str | None = Query(default=None, alias="q", min_length=1, max_length=120),
) -> list[InventoryLogItem]:
    return await list_inventory_logs(session, limit, action_type, search)


@router.get("/inventory/summary", response_model=InventorySummary)
async def summary(session: Session, _: InventoryViewer) -> InventorySummary:
    return await inventory_summary(session)


@router.post("/inventory/import-batch", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(payload: ImportBatchRequest, session: Session, _: Pharmacist) -> BatchResponse:
    return await import_batch(session, payload)


@router.get("/inventory/alerts/low-stock", response_model=list[LowStockAlert])
async def low_stock(session: Session, _: InventoryViewer) -> list[LowStockAlert]:
    return await low_stock_alerts(session)


@router.get("/inventory/alerts/expiring", response_model=list[ExpiringBatchAlert])
async def expiring(session: Session, _: InventoryViewer) -> list[ExpiringBatchAlert]:
    return await expiring_batch_alerts(session)
