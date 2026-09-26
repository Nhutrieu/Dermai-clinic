from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import the curated dermatology catalogue through the pharmacy API.")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "dermatology_catalog.json",
    )
    parser.add_argument("--base-url", default="http://localhost:8010")
    parser.add_argument("--user-id", type=uuid.UUID, required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    document = json.loads(args.catalog.read_text(encoding="utf-8"))
    products = document.get("products", [])
    if not products:
        raise SystemExit("Catalogue does not contain any products.")

    seen_skus: set[str] = set()
    for product in products:
        sku = product["sku"].strip().upper()
        if sku in seen_skus:
            raise SystemExit(f"Duplicate SKU in catalogue: {sku}")
        seen_skus.add(sku)

    if args.dry_run:
        print(f"Validated {len(products)} products from {args.catalog}")
        return

    created = skipped = 0
    endpoint = f"{args.base_url.rstrip('/')}/api/v1/inventory/products"
    for product in products:
        payload = {
            key: product[key]
            for key in ("sku", "name", "unit", "importPrice", "sellingPrice", "minThreshold")
        }
        request = Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "X-User-Id": str(args.user_id),
                "X-User-Role": "PHARMACIST",
            },
        )
        try:
            with urlopen(request, timeout=10):
                created += 1
        except HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            if error.code == 409 and "PRODUCT_SKU_EXISTS" in body:
                skipped += 1
                continue
            raise RuntimeError(f"Failed to import {product['sku']}: HTTP {error.code} {body}") from error

    print(f"Catalogue import complete: created={created}, skipped={skipped}, total={len(products)}")


if __name__ == "__main__":
    main()
