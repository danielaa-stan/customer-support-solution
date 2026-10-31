"""Validate the checked-in RAG artifacts against the shared contracts."""

import importlib.util
import json
import re
import unittest
from collections import Counter
from pathlib import Path


DATA = Path(__file__).resolve().parents[1]
CONTRACTS = DATA.parent / "contracts"
REQUIRED = {
    "refund-policy": {"2.1", "2.2", "2.3"},
    "retention-rules": {"1.1", "1.2", "1.3"},
    "cancellation": {"1.1", "1.2"},
    "plans-and-pricing": {"1.1", "1.2", "1.3"},
    "pause-policy": {"1.1"},
    "known-issues": {"1.1", "1.2", "1.3", "1.4"},
    "escalation-matrix": {"1.1", "1.2"},
    "agent-conduct": {"1.1", "1.2", "1.3"},
}
FIELDS = {"case_id", "title", "intent", "reason", "plan", "customer_message", "summary",
          "actions", "resolution", "policy_refs", "tags"}
ARGUMENTS = {
    "get_user_profile": (set(), set()),
    "get_payments": (set(), {"limit"}),
    "get_available_offers": (set(), set()),
    "pause_subscription": ({"months", "reason_code"}, set()),
    "change_plan": ({"new_plan", "reason_code"}, set()),
    "apply_retention_offer": ({"offer_code", "reason_code"}, set()),
    "issue_refund": ({"payment_id", "reason_code", "policy_ref"}, set()),
    "cancel_subscription": ({"reason_code"}, {"effective"}),
    "confirm_action": ({"pending_action_id"}, set()),
    "reject_action": ({"pending_action_id"}, set()),
    "escalate_to_human": ({"priority", "category", "summary", "suggested_action"}, set()),
}


class RagDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads((DATA / "cases.json").read_text(encoding="utf-8"))
        cls.refs = set()
        for path in (DATA / "policies").glob("*.md"):
            for section in re.findall(r"^## (\d+\.\d+) .+$", path.read_text(encoding="utf-8"), re.M):
                cls.refs.add(f"{path.stem}#{section}")
        text = (CONTRACTS / "06-transcript-and-analysis.md").read_text(encoding="utf-8")
        cls.enums = {}
        for name in ("intent", "reason_code", "resolution"):
            match = re.search(rf"`{name}` \([^\n]+\):\n(.*?)(?:\n\n|\Z)", text, re.S)
            if match is None:
                raise ValueError(f"Cannot find {name} enum in contract")
            cls.enums[name] = set(re.findall(r"`([a-z_]+)`", match[1]))
        tools_text = (CONTRACTS / "03-mcp-tools.md").read_text(encoding="utf-8")
        cls.tools = set(re.findall(r"`([a-z_]+)\(", tools_text))

    def test_policy_front_matter_and_self_contained_sections(self):
        paths = list((DATA / "policies").glob("*.md"))
        self.assertEqual({path.stem for path in paths}, set(REQUIRED))
        for path in paths:
            with self.subTest(document=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertRegex(text, rf"\A---\ndoc_id: {path.stem}\ntitle: [^\n]+\nversion: 1\.0\n---\n")
                parts = re.split(r"^## (\d+\.\d+) ([^\n]+)\n", text, flags=re.M)
                self.assertEqual(len(parts) % 3, 1)
                numbers = parts[1::3]
                self.assertEqual(len(numbers), len(set(numbers)))
                self.assertTrue(REQUIRED[path.stem] <= set(numbers))
                for section, title, body in zip(parts[1::3], parts[2::3], parts[3::3]):
                    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", body.strip())
                    self.assertTrue(2 <= len(sentences) <= 6, (section, title, len(sentences)))
                    self.assertNotRegex(body.lower(), r"see (above|below)")

    def test_count_distribution_and_unique_examples(self):
        self.assertEqual(len(self.cases), 200)
        for field in ("case_id", "customer_message"):
            self.assertEqual(len({case[field] for case in self.cases}), 200, field)
        counts = Counter(case["intent"] for case in self.cases)
        self.assertEqual(counts, {"cancel_subscription": 60, "billing_issue": 50, "refund_request": 30,
                                  "technical_issue": 30, "plan_change": 20, "account_access": 5, "other": 5})

    def test_policy_numbers_match_business_contract(self):
        contract = (CONTRACTS / "04-business-rules.md").read_text(encoding="utf-8")
        refund = (DATA / "policies/refund-policy.md").read_text(encoding="utf-8")
        retention = (DATA / "policies/retention-rules.md").read_text(encoding="utf-8")
        pricing = (DATA / "policies/plans-and-pricing.md").read_text(encoding="utf-8")
        for constant, suffix, policy in (
            ("REFUND_WINDOW_DAYS", " days", refund),
            ("AUTO_REFUND_LIMIT", " USD", refund),
            ("DUPLICATE_CHARGE_WINDOW_HOURS", " hours", refund),
            ("RETENTION_COOLDOWN_MONTHS", " months", retention),
        ):
            value = re.search(rf"\| `{constant}` \| ([\d.]+)", contract)[1]
            self.assertIn(value + suffix, policy, constant)
        for plan in ("individual", "duo", "family", "student"):
            price = re.search(rf"\| `{plan}` \| ([\d.]+) \|", contract)[1]
            self.assertIn(price + " USD", pricing)
        self.assertIn("50%", retention)
        self.assertIn("next three charges", retention)

    def check_action(self, call):
        self.assertEqual(set(call), {"tool", "args"})
        self.assertIn(call["tool"], self.tools)
        self.assertIsInstance(call["args"], dict)
        required, optional = ARGUMENTS[call["tool"]]
        self.assertTrue(required <= set(call["args"]))
        self.assertTrue(set(call["args"]) <= required | optional)
        args = call["args"]
        if "reason_code" in args:
            self.assertIn(args["reason_code"], self.enums["reason_code"])
        if "policy_ref" in args:
            self.assertIn(args["policy_ref"], self.refs)
        if call["tool"] == "pause_subscription":
            self.assertIn(args["months"], (1, 2, 3))
        if call["tool"] == "change_plan":
            self.assertIn(args["new_plan"], ("individual", "duo", "family", "student"))
        if call["tool"] == "escalate_to_human":
            self.assertIn(args["category"], self.enums["intent"])
            self.assertIn(args["priority"], ("low", "normal", "high", "urgent"))
            suggestion = args["suggested_action"]
            if suggestion is not None:
                self.assertEqual(set(suggestion), {"tool", "args", "rationale", "policy_ref"})
                self.assertIn(suggestion["policy_ref"], self.refs)
                self.check_action({"tool": suggestion["tool"], "args": suggestion["args"]})

    def test_case_contract_and_action_sequences(self):
        for case in self.cases:
            with self.subTest(case=case["case_id"]):
                self.assertEqual(set(case), FIELDS)
                self.assertRegex(case["case_id"], r"^case_\d{4}$")
                for field in ("title", "customer_message", "summary"):
                    self.assertIsInstance(case[field], str)
                    self.assertTrue(case[field].strip())
                for field, enum in (("intent", "intent"), ("reason", "reason_code"), ("resolution", "resolution")):
                    self.assertIn(case[field], self.enums[enum])
                self.assertIn(case["plan"], ("individual", "duo", "family", "student"))
                self.assertTrue(case["policy_refs"])
                self.assertTrue(set(case["policy_refs"]) <= self.refs)
                self.assertIsInstance(case["tags"], list)
                self.assertTrue(all(isinstance(tag, str) and tag for tag in case["tags"]))
                self.assertIsInstance(case["actions"], list)
                for call in case["actions"]:
                    self.check_action(call)
                    if "policy_ref" in call["args"]:
                        self.assertIn(call["args"]["policy_ref"], case["policy_refs"])
                tools = [call["tool"] for call in case["actions"]]
                if case["resolution"] == "canceled":
                    self.assertLess(tools.index("cancel_subscription"), tools.index("confirm_action"))
                    self.assertIn("later user message", case["summary"])
                if case["resolution"] == "refunded":
                    self.assertIn("issue_refund", tools)
                    self.assertNotIn("escalate_to_human", tools)
                if case["resolution"] == "escalated":
                    self.assertIn("escalate_to_human", tools)
                self.assertLessEqual(tools.count("apply_retention_offer") + tools.count("pause_subscription"), 1)
                if "apply_retention_offer" in tools:
                    self.assertLess(tools.index("get_available_offers"), tools.index("apply_retention_offer"))
                    self.assertIn("no retention offer in the preceding 12 months", case["summary"])
                    offer = next(call["args"]["offer_code"] for call in case["actions"]
                                 if call["tool"] == "apply_retention_offer")
                    self.assertIn(offer, ("discount_50_3m", "free_month_1"))
                    if offer == "discount_50_3m":
                        self.assertNotEqual(case["plan"], "student")

    def test_artifacts_are_english(self):
        paths = list((DATA / "policies").glob("*.md")) + [DATA / "cases.json"]
        for path in paths:
            self.assertNotRegex(path.read_text(encoding="utf-8"), r"[\u0400-\u04ff]", path.name)

    def test_checked_in_cases_match_generator(self):
        spec = importlib.util.spec_from_file_location("generate_cases", DATA / "generate_cases.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.build_cases(), self.cases)
        self.assertEqual(module.build_cases(), module.build_cases())


if __name__ == "__main__":
    unittest.main()
