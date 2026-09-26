from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
MIGRATION = SERVICE_ROOT / "db" / "migration" / "V1__pharmacy_inventory.sql"
FULL_SCHEMA = REPOSITORY_ROOT / "database" / "dermai_full_schema.sql"
TABLES = ("products", "product_batches", "prescriptions", "prescription_items", "inventory_logs")


def normalized_sql(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_inventory_migration_defines_pharmacy_schema_and_all_model_tables() -> None:
    sql = normalized_sql(MIGRATION)
    assert "create schema if not exists pharmacy" in sql
    for table in TABLES:
        assert f"create table if not exists {table}" in sql


def test_full_schema_includes_inventory_migration_contract() -> None:
    sql = normalized_sql(FULL_SCHEMA)
    assert "services/inventory-service/db/migration/v1__pharmacy_inventory.sql" in sql
    for table in TABLES:
        assert f"create table if not exists {table}" in sql
