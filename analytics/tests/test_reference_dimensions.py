"""Keep seeded reference dimensions aligned with the source contracts and policies."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = (ROOT / "analytics/schema.sql").read_text(encoding="utf-8")


class ReferenceDimensionTests(unittest.TestCase):
    def test_enum_dimensions_match_contract(self):
        contract = (ROOT / "contracts/06-transcript-and-analysis.md").read_text(encoding="utf-8")
        for table, enum in (("dim_intent", "intent"), ("dim_reason", "reason_code"),
                            ("dim_resolution", "resolution")):
            with self.subTest(dimension=table):
                definition = re.search(rf"`{enum}` \([^\n]+\):\n(.*?)(?:\n\n|\Z)", contract, re.S)[1]
                expected = set(re.findall(r"`([a-z_]+)`", definition))
                values = re.search(rf"INSERT INTO {table} .*?VALUES(.*?)ON CONFLICT", SCHEMA, re.S)[1]
                self.assertEqual(set(re.findall(r"\('([a-z_]+)'\)", values)), expected)

    def test_policy_dimension_matches_documents(self):
        expected = set()
        for path in (ROOT / "data/policies").glob("*.md"):
            sections = re.findall(r"^## (\d+\.\d+) .+$", path.read_text(encoding="utf-8"), re.M)
            expected.update(f"{path.stem}#{section}" for section in sections)
        actual = set(re.findall(r"\('([^']+#\d+\.\d+)',", SCHEMA))
        self.assertEqual(actual, expected)

    def test_tool_dimension_matches_contract(self):
        contract = (ROOT / "contracts/03-mcp-tools.md").read_text(encoding="utf-8")
        expected = set(re.findall(r"`([a-z_]+)\(", contract)) | {"sys_set_context"}
        actual = set(re.findall(r"\('([a-z_]+)', (?:true|false)\)", SCHEMA))
        self.assertEqual(actual, expected)

    def test_plan_prices_match_contract(self):
        contract = (ROOT / "contracts/04-business-rules.md").read_text(encoding="utf-8")
        for plan in ("individual", "duo", "family", "student"):
            with self.subTest(plan=plan):
                price, seats = re.search(rf"\| `{plan}` \| ([\d.]+) \| (\d+) \|", contract).groups()
                self.assertRegex(SCHEMA, rf"\('{plan}', '[^']+', {seats}, {re.escape(price)}\)")


if __name__ == "__main__":
    unittest.main()
