"""Opt-in PostgreSQL tests use an isolated schema and roll back all fixture objects."""

import copy
import json
import os
import unittest
import uuid
from pathlib import Path

from analytics.analysis import prepare_source, reconcile
from analytics.repository import persist

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.environ.get('RUN_POSTGRES_TESTS') == '1', 'Set RUN_POSTGRES_TESTS=1 with Docker running')
class RepositoryTests(unittest.TestCase):
    def test_reanalysis_rollback_and_identity_collisions(self):
        import psycopg
        from analytics.db import connect
        from psycopg import sql
        from dotenv import load_dotenv
        load_dotenv(ROOT / '.env')
        fixture = ROOT / 'analytics/fixtures/refund'
        doc = json.loads((fixture / 'transcript.json').read_text())
        source = prepare_source(doc, json.loads((fixture / 'source.json').read_text()))
        result = reconcile(doc, source, json.loads((fixture / 'assessment.json').read_text()))
        with connect(os.environ['ANALYTICS_DATABASE_URL']) as conn:
            with conn.transaction():
                schema = 'analytics_test_' + uuid.uuid4().hex
                conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
                conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
                baseline = (ROOT / 'analytics/schema.sql').read_text().strip()
                baseline = baseline[baseline.index('BEGIN;') + len('BEGIN;'):].removesuffix('COMMIT;')
                conn.execute(baseline, prepare=False)
                first = persist(conn, doc, source, result)
                self.assertEqual(first, persist(conn, doc, source, result))
                self.assertEqual(conn.execute('SELECT count(*) AS n FROM fact_conversation').fetchone()['n'], 1)
                totals = conn.execute('SELECT count(*) AS n, sum(refunded_amount) AS total FROM fact_tool_call').fetchone()
                self.assertEqual(totals['n'], 3)
                self.assertEqual(float(totals['total']), 4.99)
                changed = {**result, 'summary': 'Dry-run change'}
                persist(conn, doc, source, changed, dry_run=True)
                self.assertEqual(conn.execute('SELECT summary FROM fact_conversation').fetchone()['summary'], result['summary'])
                bad = {**changed, 'policy_refs': ['nonexistent#1.1']}
                with self.assertRaises(ValueError):
                    persist(conn, doc, source, bad)
                self.assertEqual(conn.execute('SELECT summary FROM fact_conversation').fetchone()['summary'], result['summary'])
                self.assertEqual(conn.execute('SELECT count(*) AS n FROM bridge_conversation_policy').fetchone()['n'], 1)
                persist(conn, doc, source, {**result, 'policy_refs': []})
                self.assertEqual(conn.execute('SELECT count(*) AS n FROM bridge_conversation_policy').fetchone()['n'], 0)
                other = {**doc, 'session_id': 'ses_other_fixture'}
                with self.assertRaises(ValueError):
                    persist(conn, other, source, result)
                self.assertEqual(conn.execute('SELECT count(*) AS n FROM fact_conversation').fetchone()['n'], 1)
                from analytics.worker import JobStore, run_once
                import tempfile
                from unittest.mock import Mock
                store = JobStore(conn)
                store.initialize()
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / (doc['session_id'] + '.json')
                    path.write_text(json.dumps(doc))
                    def process(document):
                        persist(conn, document, source, result)
                        return {'saved': True}
                    processor = Mock(side_effect=process)
                    self.assertEqual(run_once(store, Path(tmp), processor), 1)
                    self.assertEqual(run_once(store, Path(tmp), processor), 0)
                    self.assertEqual(processor.call_count, 1)
                    state = conn.execute('SELECT status, attempts FROM analytics_ingestion_job').fetchone()
                    self.assertEqual(state, {'status': 'done', 'attempts': 1})
                    conn.execute("UPDATE analytics_ingestion_job SET status='failed',attempts=1")
                    store.fail(doc['session_id'], conn.execute('SELECT fingerprint FROM analytics_ingestion_job').fetchone()['fingerprint'], 1, ValueError('Private text'))
                    self.assertIsNone(store.claim(doc['session_id'], conn.execute('SELECT fingerprint FROM analytics_ingestion_job').fetchone()['fingerprint'], 5))
                raise psycopg.Rollback()


if __name__ == '__main__':
    unittest.main()
