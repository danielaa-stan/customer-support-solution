"""Check starting-state invariants needed by the demo and generated customer records."""

import importlib.util
import json
import re
import unittest
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path


DATA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("generate_seed", DATA / "generate_seed.py")
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


def date(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class SeedDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = json.loads((DATA / "seed/seed.json").read_text(encoding="utf-8"))
        cls.users = {row["id"]: row for row in cls.seed["users"]}
        cls.subscriptions = {row["user_id"]: row for row in cls.seed["subscriptions"]}
        cls.usage = {row["user_id"]: row for row in cls.seed["usage_stats"]}

    def test_generated_file_and_reproducibility(self):
        self.assertEqual(generator.build_seed(), self.seed)
        self.assertEqual(generator.build_seed(), generator.build_seed())
        self.assertEqual(len(self.users), 44)
        self.assertEqual(len([key for key in self.users if key.startswith("u_background_")]), 40)

    def test_schema_fields_and_empty_runtime_tables(self):
        schema = (DATA.parent / "contracts/schema.sql").read_text(encoding="utf-8")
        tables = dict(re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", schema, re.S))
        self.assertEqual(set(self.seed), set(tables))
        for table, rows in self.seed.items():
            fields = set(re.findall(r"^\s{2}(\w+)\s+", tables[table], re.M))
            for row in rows:
                self.assertTrue(set(row) <= fields, (table, set(row) - fields))
        for table in ("tickets", "pending_actions", "audit_log"):
            self.assertEqual(self.seed[table], [])

    def test_prices_match_business_contract(self):
        contract = (DATA.parent / "contracts/04-business-rules.md").read_text(encoding="utf-8")
        for plan, price in generator.PRICES.items():
            expected = re.search(rf"\| `{plan}` \| ([\d.]+) \|", contract)[1]
            self.assertEqual(f"{price:.2f}", expected, plan)

    def test_ids_relationships_and_plans(self):
        self.assertEqual(len(self.seed["users"]), len(self.users))
        self.assertEqual(len({user["email"] for user in self.users.values()}), len(self.users))
        self.assertEqual(Counter(row["user_id"] for row in self.seed["subscriptions"]),
                         Counter({key: 1 for key in self.users}))
        self.assertEqual(Counter(row["user_id"] for row in self.seed["usage_stats"]),
                         Counter({key: 1 for key in self.users}))
        for table in ("subscriptions", "payments"):
            self.assertEqual(len({row["id"] for row in self.seed[table]}), len(self.seed[table]))
        for table in ("subscriptions", "payments", "usage_stats", "retention_offers_used"):
            for row in self.seed[table]:
                self.assertIn(row["user_id"], self.users)
        self.assertEqual({row["plan"] for row in self.seed["subscriptions"]}, set(generator.PRICES))
        self.assertEqual({row["status"] for row in self.seed["subscriptions"]},
                         {"active", "paused", "canceled", "past_due"})

    def test_subscription_and_payment_consistency(self):
        for subscription in self.seed["subscriptions"]:
            with self.subTest(user=subscription["user_id"]):
                user = self.users[subscription["user_id"]]
                self.assertEqual(subscription["price_amount"], generator.PRICES[subscription["plan"]])
                self.assertEqual(subscription["price_currency"], "USD")
                self.assertLessEqual(date(subscription["started_at"]), generator.DEMO_NOW)
                if subscription["plan"] == "student":
                    self.assertEqual(user["is_student"], 1)
                if subscription["status"] == "canceled":
                    self.assertIsNone(subscription["next_billing_date"])
                    self.assertLessEqual(date(subscription["cancel_at"]), generator.DEMO_NOW)
                else:
                    self.assertGreater(date(subscription["next_billing_date"]), generator.DEMO_NOW)
                if subscription["status"] == "paused":
                    self.assertEqual(subscription["next_billing_date"], subscription["paused_until"])
                    self.assertGreater(date(subscription["paused_until"]), generator.DEMO_NOW)
        for payment in self.seed["payments"]:
            with self.subTest(payment=payment["id"]):
                self.assertGreater(payment["amount"], 0)
                self.assertEqual(payment["currency"], "USD")
                self.assertLessEqual(date(self.users[payment["user_id"]]["created_at"]), date(payment["charged_at"]))
                self.assertLessEqual(date(payment["charged_at"]), generator.DEMO_NOW)
                if payment["status"] == "refunded":
                    self.assertLessEqual(date(payment["charged_at"]), date(payment["refunded_at"]))
                    self.assertLessEqual(date(payment["refunded_at"]), generator.DEMO_NOW)
                    self.assertIsNotNone(payment["refund_reason"])
                else:
                    self.assertIsNone(payment["refunded_at"])
                    self.assertIsNone(payment["refund_reason"])

    def test_demo_starting_states(self):
        family = self.subscriptions["u_demo_family"]
        self.assertEqual(family["started_at"], "2026-02-10T09:00:00Z")
        self.assertEqual(family["next_billing_date"], "2026-11-10T09:00:00Z")
        self.assertEqual(self.usage["u_demo_family"]["listening_hours_30d"], 41.5)
        self.assertEqual(self.usage["u_demo_family"]["devices_count"], 2)
        self.assertEqual(self.usage["u_demo_cancel"]["listening_hours_30d"], 1.2)
        self.assertEqual(self.usage["u_demo_cancel"]["last_active_at"], "2026-09-20T18:00:00Z")
        for key in ("u_demo_family", "u_demo_double", "u_demo_cancel", "u_demo_escalate"):
            subscription = self.subscriptions[key]
            self.assertEqual(subscription["plan"], "individual")
            self.assertEqual(subscription["status"], "active")
            self.assertEqual(subscription["discount_percent"], 0)
            self.assertIsNone(subscription["cancel_at"])
            self.assertFalse(any(row["user_id"] == key for row in self.seed["retention_offers_used"]))
        payments = {row["id"]: row for row in self.seed["payments"]}
        first, second = payments["pay_demo_dbl_1"], payments["pay_demo_dbl_2"]
        for payment in (first, second):
            self.assertEqual(payment["user_id"], "u_demo_double")
            self.assertEqual(payment["amount"], 4.99)
            self.assertEqual(payment["status"], "succeeded")
            self.assertIsNone(payment["refunded_at"])
        self.assertEqual(first["charged_at"], "2026-10-29T08:00:00Z")
        self.assertEqual(second["charged_at"], "2026-10-29T08:02:00Z")
        self.assertLessEqual(generator.DEMO_NOW - date(second["charged_at"]), timedelta(days=14))

    def test_bonus_escalation_starting_state_matches_contract(self):
        user_id = "u_demo_escalate"
        self.assertIn(user_id, self.users)
        subscription = self.subscriptions[user_id]
        self.assertEqual(subscription["id"], "sub_demo_escalate")
        self.assertEqual(subscription["started_at"], "2026-03-15T10:00:00Z")
        self.assertEqual(subscription["next_billing_date"], "2026-11-15T10:00:00Z")
        self.assertEqual(self.usage[user_id]["listening_hours_30d"], 8.0)
        payments = [row for row in self.seed["payments"] if row["id"] == "pay_demo_big"]
        self.assertEqual(len(payments), 1)
        payment = payments[0]
        self.assertEqual(payment["user_id"], user_id)
        self.assertEqual(payment["amount"], 23.97)
        self.assertEqual(payment["currency"], "USD")
        self.assertEqual(payment["kind"], "other")
        self.assertEqual(payment["status"], "succeeded")
        self.assertEqual(payment["charged_at"], "2026-10-27T10:00:00Z")
        self.assertIsNone(payment["refunded_at"])
        self.assertIsNone(payment["refund_reason"])
        contract = (DATA.parent / "contracts/04-business-rules.md").read_text(encoding="utf-8")
        limit = float(re.search(r"\| `AUTO_REFUND_LIMIT` \| ([\d.]+)", contract)[1])
        window = int(re.search(r"\| `REFUND_WINDOW_DAYS` \| (\d+)", contract)[1])
        self.assertGreater(payment["amount"], limit)
        self.assertLessEqual(generator.DEMO_NOW - date(payment["charged_at"]), timedelta(days=window))

    def test_usage_and_retention_history(self):
        for user in self.users.values():
            self.assertLessEqual(date(user["created_at"]), generator.DEMO_NOW)
            usage = self.usage[user["id"]]
            self.assertLessEqual(date(user["created_at"]), date(usage["last_active_at"]))
            self.assertLessEqual(date(usage["last_active_at"]), generator.DEMO_NOW)
            self.assertGreaterEqual(usage["listening_hours_30d"], 0)
        for offer in self.seed["retention_offers_used"]:
            self.assertLessEqual(date(self.users[offer["user_id"]]["created_at"]), date(offer["applied_at"]))
            self.assertLessEqual(date(offer["applied_at"]), generator.DEMO_NOW)
            self.assertIn(offer["offer_code"], ("discount_50_3m", "free_month_1"))
        self.assertTrue(self.seed["retention_offers_used"])


if __name__ == "__main__":
    unittest.main()
