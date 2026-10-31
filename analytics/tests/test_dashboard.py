import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from analytics.dashboard import metrics, sample  # noqa: E402

NOW = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.conv, self.calls = sample.generate(NOW)

    def test_outcome_rates_use_all_conversations(self):
        o = metrics.outcomes(self.conv)
        self.assertEqual(o["total"], len(self.conv))
        self.assertEqual(sum(o["counts"].values()), len(self.conv))
        self.assertLessEqual(o["resolved_rate"] + o["escalated_rate"] + o["abandoned_rate"], 1.0 + 1e-9)

    def test_empty_inputs_give_none_not_zero(self):
        self.assertIsNone(metrics.outcomes([])["resolved_rate"])
        self.assertIsNone(metrics.quality([])[0]["average"])

    def test_refund_totals_exclude_unverified(self):
        calls = [
            dict(tool_name="issue_refund", result_status="done", autonomy_level="auto", actor="agent",
                 refunded_amount=5, currency="USD"),
            dict(tool_name="issue_refund", result_status="done", autonomy_level="auto", actor="agent",
                 refunded_amount=None, currency=None),
            dict(tool_name="issue_refund", result_status="done", autonomy_level="confirm", actor="human",
                 refunded_amount=9, currency="USD"),
        ]
        r = metrics.auto_refunds(calls)
        self.assertEqual(r["totals"], {"USD": 5.0})
        self.assertEqual((r["count"], r["incomplete"]), (1, 1))

    def test_retention_offers_only_successful_calls(self):
        calls = [
            dict(tool_name="apply_retention_offer", result_status="done", offer_code="a", offer_title="A"),
            dict(tool_name="apply_retention_offer", result_status="denied", offer_code="a", offer_title="A"),
            dict(tool_name="pause_subscription", result_status="done", offer_code=None),
        ]
        self.assertEqual(metrics.retention_offers(calls), [{"offer": "A", "accepted": 1}])

    def test_drilldown_returns_every_row_of_session(self):
        sid = self.conv[0]["session_id"]
        rows = metrics.session_tool_calls(self.calls, sid)
        self.assertEqual(len(rows), sum(1 for t in self.calls if t["session_id"] == sid))

    def test_quality_reports_sample_size(self):
        q = {r["metric"]: r for r in metrics.quality(self.conv)}
        self.assertLessEqual(q["Correctness"]["assessed"], len(self.conv))


class AppSmokeTest(unittest.TestCase):
    def test_sample_mode_renders_without_exception(self):
        from streamlit.testing.v1 import AppTest

        os.environ["DASHBOARD_SAMPLE"] = "1"
        try:
            at = AppTest.from_file(str(ROOT / "analytics" / "dashboard" / "app.py"), default_timeout=30).run()
        finally:
            os.environ.pop("DASHBOARD_SAMPLE", None)
        self.assertFalse(at.exception, at.exception)
        self.assertTrue(any("tile" in m.value for m in at.markdown))


if __name__ == "__main__":
    unittest.main()
