"""Worker scheduling checks without model calls or a running chat UI."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from analytics.worker import finalized_documents, run_once

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/refund/transcript.json'


class MemoryStore:
    def __init__(self):
        self.jobs = {}

    def enqueue(self, session, fingerprint):
        if self.jobs.get(session, {}).get('fingerprint') != fingerprint:
            self.jobs[session] = {'fingerprint': fingerprint, 'attempts': 0, 'status': 'queued'}

    def claim(self, session, fingerprint, maximum):
        job = self.jobs[session]
        if job['status'] == 'done' or job['attempts'] >= maximum:
            return None
        job['attempts'] += 1
        job['status'] = 'processing'
        return {'attempts': job['attempts']}

    def complete(self, session, fingerprint):
        self.jobs[session]['status'] = 'done'

    def fail(self, session, fingerprint, attempts, error):
        self.jobs[session].update(status='failed', error_code=type(error).__name__)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.doc = json.loads(FIXTURE.read_text())
        self.path = self.directory / (self.doc['session_id'] + '.json')
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.doc), encoding='utf-8')

    def test_open_chats_and_temporary_files_are_ignored(self):
        self.doc.update(ended_at=None, end_reason=None)
        self.save()
        self.path.with_suffix('.json.tmp').write_text('incomplete')
        self.assertEqual(list(finalized_documents(self.directory)), [])

    def test_completed_chat_runs_once_and_changed_version_is_reprocessed(self):
        store = MemoryStore()
        processor = Mock(return_value={'saved': True})
        self.assertEqual(run_once(store, self.directory, processor), 1)
        self.assertEqual(run_once(store, self.directory, processor), 0)
        self.doc['messages'][-1]['content'] = 'Updated customer acknowledgement'
        self.save()
        self.assertEqual(run_once(store, self.directory, processor), 1)
        self.assertEqual(processor.call_count, 2)

    def test_failed_and_unsaved_jobs_are_not_marked_done(self):
        store = MemoryStore()
        processor = Mock(side_effect=ValueError('Not logged customer details'))
        for _ in range(7):
            run_once(store, self.directory, processor, max_attempts=2)
        self.assertEqual(processor.call_count, 2)
        job = store.jobs[self.doc['session_id']]
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(job['error_code'], 'ValueError')
        self.assertNotIn('Not logged', str(job))

    def test_failure_does_not_block_another_session(self):
        other = copy.deepcopy(self.doc)
        other['session_id'] = 'ses_second_fixture'
        (self.directory / (other['session_id'] + '.json')).write_text(json.dumps(other))
        processor = Mock(side_effect=[RuntimeError(), {'saved': True}])
        self.assertEqual(run_once(MemoryStore(), self.directory, processor), 1)
        self.assertEqual(processor.call_count, 2)


if __name__ == '__main__':
    unittest.main()
