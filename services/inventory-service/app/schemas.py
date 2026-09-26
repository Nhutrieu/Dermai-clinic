from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from .models import PrescriptionStatus


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class BatchOption(ApiModel):
    id: uuid.UUID
    batch_number: str
    expiry_date: date
    quantity: int
    is_fefo: bool = False


class ProductSummary(ApiModel):
    id: uuid.UUID
    sku: str
    name: str
    unit: str
    import_price: Decimal
    selling_price: Decimal
    min_threshold: int
    active: bool = True
    current_quantity: int = 0

    @field_serializer("import_price", "selling_price")
    def serialize_price(self, value: Decimal) -> int:
        return int(value)


class PendingItem(ApiModel):
    id: uuid.UUID
    product_id: uuid.UUID
    sku: str
    product_name: str
    unit: str
    quantity: int
    recommended_batch_id: uuid.UUID | None
    available_batches: list[BatchOption]


class PendingPrescription(ApiModel):
    id: uuid.UUID
    code: str
    patient_id: uuid.UUID
    patient_name: str
    doctor_id: uuid.UUID
    status: PrescriptionStatus
    paid_at: datetime
    items: list[PendingItem]


class DispenseItemRequest(ApiModel):
    item_id: uuid.UUID
    batch_id: uuid.UUID


class DispenseRequest(ApiModel):
    prescription_id: uuid.UUID
    items: list[DispenseItemRequest] = Field(min_length=1)


class DispenseResponse(ApiModel):
    prescription_id: uuid.UUID
    status: PrescriptionStatus
    dispensed_at: datetime


class ImportBatchRequest(ApiModel):
    product_id: uuid.UUID
    batch_number: str = Field(min_length=1, max_length=100)
    expiry_date: date
    quantity: int = Field(gt=0, le=1_000_000)


class BatchResponse(ApiModel):
    id: uuid.UUID
    product_id: uuid.UUID
    batch_number: str
    expiry_date: date
    quantity: int


class LowStockAlert(ApiModel):
    product_id: uuid.UUID
    sku: str
    name: str
    unit: str
    current_quantity: int
    min_threshold: int
    shortage_quantity: int


class ExpiringBatchAlert(ApiModel):
    batch_id: uuid.UUID
    product_id: uuid.UUID
    sku: str
    product_name: str
    batch_number: str
    expiry_date: date
    quantity: int
    days_remaining: int
