from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from .models import InventoryAction
from .schemas import ApiModel


class ProductCreate(ApiModel):
    sku: str = Field(min_length=2, max_length=60)
    name: str = Field(min_length=2, max_length=200)
    unit: str = Field(min_length=1, max_length=40)
    import_price: Decimal = Field(ge=0, max_digits=12, decimal_places=0)
    selling_price: Decimal = Field(ge=0, max_digits=12, decimal_places=0)
    min_threshold: int = Field(ge=0, le=1_000_000)


class ProductSaleStatusUpdate(ApiModel):
    active: bool


class BatchInventoryItem(ApiModel):
    id: uuid.UUID
    product_id: uuid.UUID
    sku: str
    product_name: str
    unit: str
    batch_number: str
    expiry_date: date
    quantity: int
    days_remaining: int
    status: str


class InventoryLogItem(ApiModel):
    id: uuid.UUID
    product_id: uuid.UUID
    batch_id: uuid.UUID
    sku: str
    product_name: str
    unit: str
    batch_number: str
    action_type: InventoryAction
    quantity_changed: int
    created_at: datetime


class InventorySummary(ApiModel):
    product_count: int
    active_batch_count: int
    available_quantity: int
    pending_prescription_count: int
    low_stock_count: int
    expiring_batch_count: int
    imports_today: int
    dispensed_today: int
