from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import get_settings
from .database import Base


SCHEMA = get_settings().database_schema


class PrescriptionStatus(str, enum.Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAID = "PAID"
    DISPENSED = "DISPENSED"
    CANCELLED = "CANCELLED"


class InventoryAction(str, enum.Enum):
    IMPORT = "IMPORT"
    DISPENSE = "DISPENSE"


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("import_price >= 0", name="ck_products_import_price"),
        CheckConstraint("selling_price >= 0", name="ck_products_selling_price"),
        CheckConstraint("min_threshold >= 0", name="ck_products_min_threshold"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sku: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    import_price: Mapped[Decimal] = mapped_column(Numeric(12, 0), nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 0), nullable=False)
    min_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    batches: Mapped[list[ProductBatch]] = relationship(back_populates="product", lazy="selectin")


class ProductBatch(Base):
    __tablename__ = "product_batches"
    __table_args__ = (
        UniqueConstraint("product_id", "batch_number", name="uq_product_batch_number"),
        Index("ix_product_batches_fefo", "product_id", "expiry_date"),
        CheckConstraint("quantity >= 0", name="ck_product_batches_quantity"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    batch_number: Mapped[str] = mapped_column(String(100), nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    product: Mapped[Product] = relationship(back_populates="batches")


class Prescription(Base):
    __tablename__ = "prescriptions"
    __table_args__ = (
        Index("ix_prescriptions_status_paid_at", "status", "paid_at"),
        CheckConstraint(
            "status IN ('PENDING_PAYMENT', 'PAID', 'DISPENSED', 'CANCELLED')",
            name="ck_pharmacy_prescriptions_status",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    patient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    doctor_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[PrescriptionStatus] = mapped_column(
        Enum(PrescriptionStatus, native_enum=False, length=30), nullable=False, default=PrescriptionStatus.PENDING_PAYMENT
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispensed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispensed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)

    items: Mapped[list[PrescriptionItem]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan", lazy="selectin"
    )


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_prescription_items_quantity"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    prescription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.prescriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.products.id", ondelete="RESTRICT"), nullable=False
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.product_batches.id", ondelete="RESTRICT")
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    prescription: Mapped[Prescription] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(lazy="joined")
    batch: Mapped[ProductBatch | None] = relationship(lazy="joined")


class InventoryLog(Base):
    __tablename__ = "inventory_logs"
    __table_args__ = (
        Index("ix_inventory_logs_product_created", "product_id", "created_at"),
        CheckConstraint("action_type IN ('IMPORT', 'DISPENSE')", name="ck_inventory_logs_action_type"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.products.id", ondelete="RESTRICT"), nullable=False
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.product_batches.id", ondelete="RESTRICT"), nullable=False
    )
    action_type: Mapped[InventoryAction] = mapped_column(
        Enum(InventoryAction, native_enum=False, length=20), nullable=False
    )
    quantity_changed: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
