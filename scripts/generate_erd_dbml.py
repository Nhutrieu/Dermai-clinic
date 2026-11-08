"""Build importable DBML diagrams from the documented PostgreSQL schema.

Run from the repository root: python scripts/generate_erd_dbml.py
The physical diagram contains only PostgreSQL foreign keys. The logical
diagram adds application-level UUID references documented in the ERD guide.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "docs" / "database-schema-reference.md"
GUIDE = ROOT / "docs" / "database-erd-guide.md"
OUTPUT = ROOT / "database"

TABLE_RE = re.compile(r"^#### `([a-z_]+\.[a-z_]+)`$")
COLUMN_RE = re.compile(r"^\| `([a-z0-9_]+)` \| `([^`]+)` \| (Không|Có) \| `?([^|`]+)`? \|$")
KEY_RE = re.compile(r"^- \*\*(PK|UNIQUE)\*\* `[^`]+`: `(?:PRIMARY KEY|UNIQUE) \(([^)]+)\)`$")
FK_RE = re.compile(
    r"^- \*\*FK\*\* `[^`]+`: `FOREIGN KEY \(([^)]+)\) "
    r"REFERENCES ([a-z_]+\.[a-z_]+)\(([^)]+)\)(?: ON DELETE [A-Z ]+)?`$"
)
UNIQUE_INDEX_RE = re.compile(
    r"^- `[^`]+`: `CREATE UNIQUE INDEX [^ ]+ ON [a-z_]+\.[a-z_]+ "
    r"USING btree \(([^)]+)\)(?: WHERE .+)?`$"
)
SIMPLE_COLUMN_RE = re.compile(r"^[a-z_]+(?:, [a-z_]+)*$")


@dataclass
class Table:
    name: str
    columns: list[tuple[str, str, bool]] = field(default_factory=list)
    primary_key: tuple[str, ...] = ()
    uniques: set[tuple[str, ...]] = field(default_factory=set)


def parse_reference() -> tuple[dict[str, Table], set[tuple[str, str]]]:
    tables: dict[str, Table] = {}
    refs: set[tuple[str, str]] = set()
    current: Table | None = None
    in_indexes = False
    for line in REFERENCE.read_text(encoding="utf-8").splitlines():
        if match := TABLE_RE.fullmatch(line):
            current = Table(match.group(1))
            tables[current.name] = current
            in_indexes = False
            continue
        if current is None:
            continue
        if line == "Chỉ mục bổ sung:":
            in_indexes = True
            continue
        if match := COLUMN_RE.fullmatch(line):
            current.columns.append((match.group(1), match.group(2), match.group(3) == "Không"))
        elif match := KEY_RE.fullmatch(line):
            cols = tuple(part.strip() for part in match.group(2).split(","))
            if match.group(1) == "PK":
                current.primary_key = cols
            else:
                current.uniques.add(cols)
        elif match := FK_RE.fullmatch(line):
            source_cols = [part.strip() for part in match.group(1).split(",")]
            target_cols = [part.strip() for part in match.group(3).split(",")]
            if len(source_cols) != 1 or len(target_cols) != 1:
                raise ValueError(f"Unsupported composite FK in {current.name}: {line}")
            refs.add((f"{current.name}.{source_cols[0]}", f"{match.group(2)}.{target_cols[0]}"))
        elif in_indexes and (match := UNIQUE_INDEX_RE.fullmatch(line)):
            cols = match.group(1)
            # A partial unique index cannot be shown as unconditional uniqueness.
            if " WHERE " not in line and SIMPLE_COLUMN_RE.fullmatch(cols):
                current.uniques.add(tuple(cols.split(", ")))
    return tables, refs


def parse_logical_refs(physical: set[tuple[str, str]]) -> set[tuple[str, str]]:
    refs: set[tuple[str, str]] = set()
    in_section = False
    for line in GUIDE.read_text(encoding="utf-8").splitlines():
        if line.startswith("## Liên kết logic giữa schema"):
            in_section = True
        elif line.startswith("## Liên kết logic trong cùng schema"):
            in_section = False
        if not in_section or not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        source = cells[0].strip("` ?")
        target = cells[1].strip("` ?")
        if source.count(".") == 2 and target.count(".") == 2 and (source, target) not in physical:
            refs.add((source, target))
    # These same-schema links are explicitly documented as logical references.
    refs.update({
        ("appointment.support_messages.patient_identity_id", "appointment.support_conversations.patient_identity_id"),
        ("prescription.invoices.prescription_id", "prescription.prescriptions.id"),
        ("prescription.prescription_items.medicine_id", "prescription.medicines.id"),
        ("prescription.invoice_items.medicine_id", "prescription.medicines.id"),
        ("prescription.inventory_movements.medicine_id", "prescription.medicines.id"),
    })
    return refs - physical


def dbml_type(postgres_type: str) -> str:
    return (
        postgres_type.replace("character varying", "varchar")
        .replace("timestamp with time zone", "timestamptz")
        .replace("time without time zone", "time")
        .replace("double precision", "double")
    )


def render(tables: dict[str, Table], physical: set[tuple[str, str]], logical: set[tuple[str, str]]) -> str:
    lines = [
        "// DermAI Clinic ERD. Generated by scripts/generate_erd_dbml.py.",
        "// Source: docs/database-schema-reference.md and docs/database-erd-guide.md.",
        "// Columns, primary keys, unconditional unique keys and physical FKs reflect the database.",
        "// CHECK constraints, defaults, ordinary indexes and partial unique indexes are omitted for readability.",
        "// LOGICAL refs, when present, are application-level UUID links, NOT PostgreSQL FKs.",
        "",
        "Project dermai_clinic {",
        "  database_type: 'PostgreSQL'",
        "}",
        "",
    ]
    for table in tables.values():
        lines.append(f"Table {table.name} {{")
        for name, postgres_type, not_null in table.columns:
            flags = []
            if len(table.primary_key) == 1 and name == table.primary_key[0]:
                flags.append("pk")
            if not_null:
                flags.append("not null")
            if (name,) in table.uniques:
                flags.append("unique")
            suffix = f" [{', '.join(flags)}]" if flags else ""
            lines.append(f"  {name} {dbml_type(postgres_type)}{suffix}")
        indexes = []
        if len(table.primary_key) > 1:
            indexes.append(f"    ({', '.join(table.primary_key)}) [pk]")
        for columns in sorted(table.uniques):
            if len(columns) > 1:
                indexes.append(f"    ({', '.join(columns)}) [unique]")
        if indexes:
            lines += ["", "  indexes {", *indexes, "  }"]
        lines += ["}", ""]
    lines += ["// Physical PostgreSQL foreign keys"]
    for source, target in sorted(physical):
        source_table, source_col = source.rsplit(".", 1)
        unique = (source_col,) in tables[source_table].uniques or tables[source_table].primary_key == (source_col,)
        lines.append(f"Ref: {source} {'-' if unique else '>'} {target}")
    if logical:
        lines += ["", "// LOGICAL ONLY: references below are not enforced by PostgreSQL"]
        for source, target in sorted(logical):
            source_table, source_col = source.rsplit(".", 1)
            unique = (source_col,) in tables[source_table].uniques or tables[source_table].primary_key == (source_col,)
            lines.append(f"Ref: {source} {'-' if unique else '>'} {target} // LOGICAL")
    return "\n".join(lines) + "\n"


def main() -> None:
    tables, physical = parse_reference()
    logical = parse_logical_refs(physical)
    if len(tables) != 48 or len({name.split(".")[0] for name in tables}) != 9:
        raise ValueError("Unexpected table or schema count; refresh the database reference first")
    for source, target in physical | logical:
        for endpoint in (source, target):
            table, column = endpoint.rsplit(".", 1)
            if table not in tables or column not in {item[0] for item in tables[table].columns}:
                raise ValueError(f"Unknown ERD endpoint: {endpoint}")
    (OUTPUT / "dermai_erd.dbml").write_text(render(tables, physical, set()), encoding="utf-8")
    (OUTPUT / "dermai_erd_with_logical_refs.dbml").write_text(render(tables, physical, logical), encoding="utf-8")
    print(f"Generated {len(tables)} tables, {len(physical)} physical FKs, {len(logical)} logical refs")


if __name__ == "__main__":
    main()
