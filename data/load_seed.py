"""Load the local PostgreSQL support database atomically without overwriting data."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from validate_seed import ROOT, TABLES, insert_statements


def empty_database_guard():
    checks = " OR ".join(f'EXISTS (SELECT 1 FROM "{table}")' for table in TABLES)
    return (
        "DO $seed_guard$ BEGIN IF " + checks + " THEN "
        "RAISE EXCEPTION 'Refusing to seed a nonempty support database; no data was changed.'; "
        "END IF; END $seed_guard$;"
    )


def load_statements(seed, schema="public"):
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", schema):
        raise ValueError("Invalid target schema")
    inserts = insert_statements(seed)
    if any(seed.get(table) for table in ("tickets", "pending_actions", "audit_log")):
        raise ValueError("Runtime tables must be empty in starting seed data")
    if not seed["users"]:
        raise ValueError("Seed must contain at least one customer")
    tables = ", ".join('"' + table + '"' for table in TABLES)
    statements = [f'SET LOCAL search_path TO "{schema}";',
                  "SET LOCAL standard_conforming_strings = on;",
                  "SET LOCAL lock_timeout = '5s';",
                  f"LOCK TABLE {tables} IN EXCLUSIVE MODE;", empty_database_guard()]
    statements.extend(inserts)
    # Imported identity values must not collide with future server-generated IDs.
    statements.append(
        "SELECT setval(pg_get_serial_sequence('retention_offers_used', 'id'), "
        "COALESCE((SELECT max(id) FROM retention_offers_used), 1), "
        "EXISTS (SELECT 1 FROM retention_offers_used));"
    )
    return statements


def load_sql(seed, dry_run=False):
    end = "ROLLBACK;" if dry_run else "COMMIT;"
    return "\n".join(["BEGIN;", *load_statements(seed), end]) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=ROOT / "data/seed/seed.json")
    parser.add_argument("--dry-run", action="store_true", help="Validate inserts, then roll them back")
    args = parser.parse_args()
    try:
        seed = json.loads(args.seed.read_text(encoding="utf-8"))
        sql = load_sql(seed, args.dry_run)
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "db", "psql", "-X", "-U", "support_app", "-d", "support",
             "-v", "ON_ERROR_STOP=1", "--quiet"],
            input=sql, text=True, encoding="utf-8", capture_output=True, cwd=ROOT,
        )
        if result.returncode:
            print(result.stderr.strip() or "Seed loading failed; check Docker and the database schema.", file=sys.stderr)
            return 1
    except (OSError, ValueError) as error:
        print(f"Seed loading failed: {error}", file=sys.stderr)
        return 1
    if args.dry_run:
        print(f"Dry run passed for {len(seed['users'])} customers; no customer records were saved.")
    else:
        print(f"Loaded {len(seed['users'])} customers and {len(seed['payments'])} payments into support.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
