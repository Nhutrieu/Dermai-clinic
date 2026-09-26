import uuid
from datetime import date, timedelta

from app.models import ProductBatch
from app.service import eligible_batches


def batch(number: str, expires_in: int, quantity: int) -> ProductBatch:
    return ProductBatch(
        id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        batch_number=number,
        expiry_date=date.today() + timedelta(days=expires_in),
        quantity=quantity,
    )


def test_eligible_batches_orders_fefo_and_excludes_expired_or_empty() -> None:
    options = [batch("LATE", 90, 4), batch("EARLY", 12, 2), batch("EMPTY", 5, 0), batch("EXPIRED", -1, 10)]

    result = eligible_batches(options, required_quantity=1)

    assert [item.batch_number for item in result] == ["EARLY", "LATE"]
