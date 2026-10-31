"""Emit a PostgreSQL validation transaction that leaves live support tables untouched."""

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TABLES = ("users", "subscriptions", "payments", "usage_stats", "retention_offers_used",
          "tickets", "pending_actions", "audit_log")


def sql_literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Seed numbers must be finite")
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    raise ValueError(f"Unsupported seed value: {type(value).__name__}")


def insert_statements(seed):
    if not isinstance(seed, dict) or set(seed) != set(TABLES):
        raise ValueError("Seed must contain exactly the eight support tables")
    statements = []
    for table in TABLES:
        if not isinstance(seed[table], list):
            raise ValueError(f"Seed table {table} must be an array")
        for row in seed[table]:
            # Row keys originate in the generator; reject unsafe or unexpected identifiers.
            if not isinstance(row, dict) or not row or any(
                not isinstance(key, str) or not key.replace("_", "").isalnum() for key in row
            ):
                raise ValueError(f"Invalid column names in {table}")
            columns = ", ".join('"' + key + '"' for key in row)
            values = ", ".join(sql_literal(value) for value in row.values())
            statements.append(f'INSERT INTO "{table}" ({columns}) VALUES ({values});')
    return statements


def validation_sql(seed):
    schema = (ROOT / "contracts/schema.sql").read_text(encoding="utf-8")
    statements = ["BEGIN;", "CREATE SCHEMA seed_validation;",
                  "SET LOCAL search_path TO seed_validation;",
                  "SET LOCAL standard_conforming_strings = on;", schema]
    statements.extend(insert_statements(seed))
    statements.append("SELECT 'Seed schema validation passed' AS result, "
                      "(SELECT count(*) FROM users) AS users, "
                      "(SELECT count(*) FROM payments) AS payments;")
    statements.append("ROLLBACK;")
    return "\n".join(statements) + "\n"


if __name__ == "__main__":
    seed = json.loads((ROOT / "data/seed/seed.json").read_text(encoding="utf-8"))
    print(validation_sql(seed), end="")
