"""Loader safety checks; opt-in PostgreSQL tests never commit fixture data."""

import copy
import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


DATA = Path(__file__).resolve().parents[1]


def import_script(name):
    spec = importlib.util.spec_from_file_location(name, DATA / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = import_script("validate_seed")
with patch.dict(sys.modules, {"validate_seed": validator}):
    loader = import_script("load_seed")


class SeedLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = json.loads((DATA / "seed/seed.json").read_text(encoding="utf-8"))

    def test_invalid_input_is_rejected_before_database_access(self):
        for value in ({}, [], {"users": []}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                loader.load_sql(value)
        for table in ("tickets", "pending_actions", "audit_log"):
            seed = copy.deepcopy(self.seed)
            seed[table] = [{"id": "not_initial_data"}]
            with self.assertRaisesRegex(ValueError, "Runtime tables"):
                loader.load_sql(seed)
        with self.assertRaisesRegex(ValueError, "Invalid target schema"):
            loader.load_statements(self.seed, schema='public; COMMIT;')

    def test_nonfinite_numbers_and_unsafe_columns_are_rejected(self):
        seed = copy.deepcopy(self.seed)
        seed["payments"][0]["amount"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite"):
            loader.load_sql(seed)
        seed = copy.deepcopy(self.seed)
        seed["users"][0]['name); COMMIT; --'] = "unsafe column"
        with self.assertRaisesRegex(ValueError, "column"):
            loader.load_sql(seed)

    @unittest.skipUnless(os.environ.get("RUN_POSTGRES_TESTS") == "1", "Set RUN_POSTGRES_TESTS=1 with Docker running")
    def test_atomic_loading_and_nonempty_guard_in_postgres(self):
        schema = (DATA.parent / "contracts/schema.sql").read_text(encoding="utf-8")
        seed = copy.deepcopy(self.seed)
        seed["users"][0]["name"] = "O'Neil; COMMIT; --"
        start = "BEGIN; CREATE SCHEMA seed_loader_check; SET LOCAL search_path TO seed_loader_check;\n" + schema
        load = "\n".join(loader.load_statements(seed, schema="seed_loader_check"))
        guard = validator.sql_literal(loader.empty_database_guard())
        assertion = f"""
DO $check$
BEGIN
  IF (SELECT count(*) FROM users) <> {len(seed['users'])} THEN
    RAISE EXCEPTION 'Wrong number of customers loaded';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM users WHERE name = 'O''Neil; COMMIT; --') THEN
    RAISE EXCEPTION 'Customer text did not round-trip safely';
  END IF;
  BEGIN
    EXECUTE {guard};
    RAISE EXCEPTION 'Nonempty database was accepted';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM NOT LIKE 'Refusing to seed a nonempty support database%' THEN RAISE; END IF;
  END;
END $check$;
ROLLBACK;
"""
        command = ["docker", "compose", "exec", "-T", "db", "psql", "-X", "-U", "support_app",
                   "-d", "support", "-v", "ON_ERROR_STOP=1", "--quiet"]

        def run(sql):
            return subprocess.run(command, cwd=DATA.parent, input=sql, text=True, encoding="utf-8", capture_output=True)

        result = run(start + "\n" + load + "\n" + assertion)
        self.assertEqual(result.returncode, 0, result.stderr)

        # A late foreign-key failure must roll back earlier inserts and schema creation.
        invalid = copy.deepcopy(seed)
        invalid["payments"][-1]["user_id"] = "u_nonexistent"
        result = run(start + "\n" + "\n".join(loader.load_statements(invalid, schema="seed_loader_check")) + "\nCOMMIT;")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("foreign key constraint", result.stderr)
        result = run("SELECT to_regnamespace('seed_loader_check') IS NULL AS rolled_back;")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"\bt\b")


if __name__ == "__main__":
    unittest.main()
