"""Evidence and model-contract tests requiring neither a model nor a database."""

import copy
import json
import unittest
from pathlib import Path

from analytics.analysis import OpenConversation, prepare_source, reconcile, validate_transcript

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/refund'


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads((FIXTURE / 'transcript.json').read_text())
        self.source = json.loads((FIXTURE / 'source.json').read_text())
        self.estimate = json.loads((FIXTURE / 'assessment.json').read_text())

    def test_verified_refund_and_retry_are_counted_once(self):
        source = prepare_source(self.doc, self.source)
        result = reconcile(self.doc, source, self.estimate)
        self.assertEqual(result['resolution'], 'refunded')
        self.assertEqual(result['plan'], 'individual')
        amounts = [r['refunded_amount'] for r in source['audit'] if r['refunded_amount'] is not None]
        self.assertEqual(amounts, ['4.99'])
        self.assertNotIn('args', self.source['audit'][0])

    def test_open_transcript_is_skipped(self):
        self.doc['ended_at'] = None
        self.doc['end_reason'] = None
        with self.assertRaises(OpenConversation):
            validate_transcript(self.doc)

    def test_sequence_and_time_must_be_valid(self):
        self.doc['messages'][0]['seq'] = 2
        with self.assertRaises(ValueError):
            validate_transcript(self.doc)
        self.doc['messages'][0]['seq'] = 1
        self.doc['messages'][0]['ts'] = '2026-10-30T12:00:00Z'
        with self.assertRaises(ValueError):
            validate_transcript(self.doc)

    def test_cross_session_and_cross_customer_evidence_is_rejected(self):
        for field in ('user_id', 'session_id'):
            bad = copy.deepcopy(self.source)
            bad['audit'][0][field] = 'different'
            with self.subTest(field=field), self.assertRaises(ValueError):
                prepare_source(self.doc, bad)

    def test_refund_claim_requires_a_matching_payment(self):
        for field, value in [('status', 'succeeded'), ('refunded_at', '2026-10-30T12:00:00Z'),
                             ('refund_reason', 'other'), ('amount', -1)]:
            bad = copy.deepcopy(self.source)
            bad['payments'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                prepare_source(self.doc, bad)

    def test_invalid_model_values_are_rejected(self):
        source = prepare_source(self.doc, self.source)
        for field, value in [('sentiment_start', True), ('churn_risk', float('nan')),
                             ('primary_intent', 'invented'), ('policy_refs', ['agent-conduct#1.1']),
                             ('resolution', 'retained')]:
            bad = copy.deepcopy(self.estimate)
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                reconcile(self.doc, source, bad)

    def test_unassessed_values_remain_null(self):
        self.estimate.update(sentiment_start=None, sentiment_end=None, churn_risk=None)
        self.estimate['quality'] = dict.fromkeys(self.estimate['quality'])
        result = reconcile(self.doc, prepare_source(self.doc, self.source), self.estimate)
        self.assertIsNone(result['sentiment_start'])
        self.assertIsNone(result['quality']['correctness'])

    def test_cancellation_requires_confirmed_action_not_proposal(self):
        self.source['audit'] = [self.source['audit'][0], {
            **self.source['audit'][1], 'tool': 'cancel_subscription', 'result_status': 'pending_confirmation',
            'args_json': '{}', 'reason_code': 'low_usage', 'policy_ref': 'cancellation#1.1'}]
        self.doc['end_reason'] = 'user_left'
        self.estimate.update(primary_intent='cancel_subscription', underlying_reason='low_usage',
                             resolution='abandoned', policy_refs=['cancellation#1.1'])
        source = prepare_source(self.doc, self.source)
        self.assertEqual(reconcile(self.doc, source, self.estimate)['resolution'], 'abandoned')
        self.source['audit'].append({**self.source['audit'][1], 'id': -910001, 'tool': 'confirm_action',
                                    'result_status': 'done', 'args_json': '{"pending_action_id":"pa_fixture"}'})
        with self.assertRaises(ValueError):
            prepare_source(self.doc, self.source)
        self.source['pending'] = [{'id': 'pa_fixture', 'session_id': self.doc['session_id'],
                                   'user_id': self.doc['user_id'], 'tool': 'cancel_subscription', 'status': 'confirmed'}]
        self.estimate['resolution'] = 'canceled'
        self.assertEqual(reconcile(self.doc, prepare_source(self.doc, self.source), self.estimate)['resolution'], 'canceled')

    def test_absent_audit_and_missing_plan_evidence(self):
        bad = copy.deepcopy(self.source)
        bad['audit'] = []
        with self.assertRaises(ValueError):
            prepare_source(self.doc, bad)
        self.doc['messages'][2]['content'].pop('audit_id')
        result = reconcile(self.doc, prepare_source(self.doc, self.source), self.estimate)
        self.assertEqual(result['plan'], 'unknown')

    def test_user_left_is_not_automatically_resolved(self):
        self.source['audit'] = self.source['audit'][:1]
        self.doc['end_reason'] = 'user_left'
        self.estimate.update(resolution='abandoned', policy_refs=[])
        self.assertEqual(reconcile(self.doc, prepare_source(self.doc, self.source), self.estimate)['resolution'], 'abandoned')

    def test_conversation_without_backend_tools_can_be_analyzed(self):
        self.source['audit'] = []
        self.doc['messages'] = [
            {**self.doc['messages'][0], 'content': 'Thank you for explaining the plans.'},
            {**self.doc['messages'][-1], 'seq': 2, 'role': 'assistant', 'content': 'You are welcome.'},
        ]
        self.estimate.update(primary_intent='other', underlying_reason='other', resolution='resolved_auto', policy_refs=[])
        self.assertEqual(reconcile(self.doc, prepare_source(self.doc, self.source), self.estimate)['resolution'], 'resolved_auto')


if __name__ == '__main__':
    unittest.main()
