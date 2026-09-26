from __future__ import annotations

import argparse
import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


DEFAULT_PLAN = Path(__file__).resolve().parents[1] / "data" / "simulated_batch_plan.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create deterministic simulated inventory batches through the pharmacy API."
    )
    parser.add_argument("--base-url", default="http://localhost:8010")
    parser.add_argument("--user-id", type=uuid.UUID, required=True)
    parser.add_argument("--plan-output", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--regenerate", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def request_json(
    url: str,
    user_id: uuid.UUID,
    *,
    payload: dict[str, Any] | None = None,
) -> Any:
    headers = {
        "Accept": "application/json",
        "X-User-Id": str(user_id),
        "X-User-Role": "PHARMACIST",
    }
    data = None
    method = "GET"
    if payload is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        method = "POST"

    request = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code} calling {url}: {body}") from error


def batch_number(sku: str, suffix: str) -> str:
    safe_sku = re.sub(r"[^A-Z0-9]+", "-", sku.upper()).strip("-")
    return f"SIM-DEMO-{safe_sku}-{suffix}"[:100]


def build_plan(products: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    ordered = sorted(products, key=lambda product: product["sku"])
    low_stock_candidates = [
        product["id"]
        for product in ordered
        if int(product["currentQuantity"]) == 0 and int(product["minThreshold"]) > 1
    ]
    low_stock_ids = set(low_stock_candidates[::7][:7])

    batches: list[dict[str, Any]] = []
    for index, product in enumerate(ordered, start=1):
        threshold = int(product["minThreshold"])
        is_low_stock = product["id"] in low_stock_ids
        is_expiring = index % 5 == 0
        current_quantity = int(product["currentQuantity"])

        if is_low_stock:
            primary_quantity = max(1, threshold - 1)
        else:
            desired_stock = max(20, threshold * 2)
            primary_quantity = max(1, desired_stock - current_quantity)

        primary_expiry = today + (
            timedelta(days=20)
            if is_expiring
            else timedelta(days=180 + (index % 6) * 30)
        )
        batches.append(
            {
                "productId": product["id"],
                "sku": product["sku"],
                "productName": product["name"],
                "unit": product["unit"],
                "batchNumber": batch_number(product["sku"], "A"),
                "expiryDate": primary_expiry.isoformat(),
                "quantity": primary_quantity,
                "scenario": "LOW_STOCK" if is_low_stock else ("EXPIRING_30_DAYS" if is_expiring else "NORMAL"),
            }
        )

        if index % 4 == 0 and not is_low_stock:
            batches.append(
                {
                    "productId": product["id"],
                    "sku": product["sku"],
                    "productName": product["name"],
                    "unit": product["unit"],
                    "batchNumber": batch_number(product["sku"], "B"),
                    "expiryDate": (today + timedelta(days=420 + (index % 4) * 30)).isoformat(),
                    "quantity": max(10, threshold * 2),
                    "scenario": "FEFO_SECOND_BATCH",
                }
            )

    return batches


def main() -> None:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    products = request_json(f"{base_url}/api/v1/inventory/products", args.user_id)
    existing_batches = request_json(f"{base_url}/api/v1/inventory/batches", args.user_id)
    if not products:
        raise SystemExit("No products found. Import the dermatology catalogue first.")

    existing_numbers = {batch["batchNumber"] for batch in existing_batches}
    if args.plan_output.exists() and not args.regenerate:
        document = json.loads(args.plan_output.read_text(encoding="utf-8"))
        plan = document["batches"]
    else:
        today = date.today()
        plan = build_plan(products, today)
        document = {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "simulationDate": today.isoformat(),
            "note": 'Dữ liệu lô mô phỏng cho FEFO, cảnh báo cận hạn và cảnh báo tồn thấp; nhận diện bằng tiền tố SIM-.',
            "batches": plan,
        }
        args.plan_output.parent.mkdir(parents=True, exist_ok=True)
        args.plan_output.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if args.dry_run:
        print(f"Validated plan with {len(plan)} batches; output={args.plan_output}")
        return

    created = skipped = 0
    endpoint = f"{base_url}/api/v1/inventory/import-batch"
    for batch in plan:
        if batch["batchNumber"] in existing_numbers:
            skipped += 1
            continue
        payload = {
            key: batch[key]
            for key in ("productId", "batchNumber", "expiryDate", "quantity")
        }
        request_json(endpoint, args.user_id, payload=payload)
        created += 1

    print(
        f"Simulated batch import complete: created={created}, skipped={skipped}, "
        f"planned={len(plan)}, output={args.plan_output}"
    )


if __name__ == "__main__":
    main()
