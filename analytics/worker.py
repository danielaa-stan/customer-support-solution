"""Poll finalized transcripts and process them with durable retry checkpoints."""

import argparse
import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path

from analytics.analysis import ROOT, OpenConversation, validate_transcript
from analytics.analyzer import analyze_document
from analytics.db import connect

LOG = logging.getLogger(__name__)
JOB_SCHEMA = '''CREATE TABLE IF NOT EXISTS analytics_ingestion_job (
    session_id TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued','processing','done','failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    error_code TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)'''


def finalized_documents(directory):
    for path in sorted(directory.glob('*.json')):
        try:
            raw = path.read_bytes()
            doc = json.loads(raw)
            validate_transcript(doc)
            if path.stem != doc['session_id']:
                raise ValueError('Filename must match session_id')
            yield doc, hashlib.sha256(raw).hexdigest()
        except OpenConversation:
            continue
        except (OSError, ValueError, KeyError, TypeError):
            # Do not log customer text or untrusted file names.
            LOG.warning('Skipped an unreadable or invalid transcript file')


class JobStore:
    def __init__(self, connection):
        self.connection = connection

    def initialize(self):
        self.connection.execute(JOB_SCHEMA)

    def acquire(self):
        row = self.connection.execute("SELECT pg_try_advisory_lock(hashtextextended('analytics_ingestion_worker', 0)) AS acquired").fetchone()
        if row['acquired']:
            self.connection.execute("UPDATE analytics_ingestion_job SET status='failed', error_code='Interrupted', next_attempt_at=now() WHERE status='processing'")
        return row['acquired']

    def enqueue(self, session, fingerprint):
        self.connection.execute('''INSERT INTO analytics_ingestion_job(session_id,fingerprint,status)
            VALUES (%s,%s,'queued') ON CONFLICT(session_id) DO UPDATE SET
            fingerprint=EXCLUDED.fingerprint,status='queued',attempts=0,next_attempt_at=now(),error_code=NULL,updated_at=now()
            WHERE analytics_ingestion_job.fingerprint<>EXCLUDED.fingerprint''', (session, fingerprint))

    def claim(self, session, fingerprint, max_attempts):
        return self.connection.execute('''UPDATE analytics_ingestion_job SET status='processing',
            attempts=attempts+1,updated_at=now() WHERE session_id=%s AND fingerprint=%s
            AND status IN ('queued','failed') AND attempts<%s AND next_attempt_at<=now()
            RETURNING attempts''', (session, fingerprint, max_attempts)).fetchone()

    def complete(self, session, fingerprint):
        self.connection.execute('''UPDATE analytics_ingestion_job SET status='done',error_code=NULL,updated_at=now()
            WHERE session_id=%s AND fingerprint=%s''', (session, fingerprint))

    def fail(self, session, fingerprint, attempts, error):
        delay = min(300, 30 * (2 ** min(attempts - 1, 4)))
        self.connection.execute('''UPDATE analytics_ingestion_job SET status='failed',error_code=%s,
            next_attempt_at=now() + %s * interval '1 second',updated_at=now()
            WHERE session_id=%s AND fingerprint=%s''', (type(error).__name__, delay, session, fingerprint))


def run_once(store, directory, processor=analyze_document, max_attempts=5):
    completed = 0
    for doc, fingerprint in finalized_documents(directory):
        session = doc['session_id']
        store.enqueue(session, fingerprint)
        claimed = store.claim(session, fingerprint, max_attempts)
        if claimed is None:
            continue
        try:
            result = processor(doc)
            if not result.get('saved'):
                raise ValueError('Analyzer did not commit a result')
            store.complete(session, fingerprint)
            completed += 1
        except Exception as error:
            store.fail(session, fingerprint, claimed['attempts'], error)
            LOG.warning('Analytics job failed (%s); recorded for bounded retry', type(error).__name__)
    return completed


def serve(directory, once=False, poll_seconds=5):
    # Keep a dedicated connection open for the single-worker advisory lock.
    with connect(os.environ['ANALYTICS_DATABASE_URL']) as connection:
        store = JobStore(connection)
        store.initialize()
        if not store.acquire():
            LOG.info('Another analytics worker is already active')
            return
        while True:
            count = run_once(store, directory)
            if count:
                LOG.info('Analyzed %d finalized conversation(s)', count)
            if once:
                return
            time.sleep(poll_seconds)


def background_loop(directory):
    while True:
        try:
            serve(directory)
            return  # A separately launched worker holds the lock.
        except Exception as error:
            LOG.warning('Analytics worker unavailable (%s); reconnecting in 30 seconds', type(error).__name__)
            time.sleep(30)


def start_background_worker():
    """Called once per Streamlit process via cache_resource; never blocks a chat turn."""
    if os.environ.get('ANALYTICS_ENABLED', 'true').lower() not in {'1', 'true', 'yes'}:
        return None
    if not all(os.environ.get(key) for key in ('SUPPORT_READONLY_DATABASE_URL', 'ANALYTICS_DATABASE_URL')):
        LOG.warning('Analytics disabled: both database URLs must be configured')
        return None
    directory = Path(os.environ.get('TRANSCRIPTS_DIR', ROOT / 'runtime/transcripts'))
    if not directory.is_absolute():
        directory = ROOT / directory
    thread = threading.Thread(target=background_loop, args=(directory,), name='analytics-worker', daemon=True)
    thread.start()
    return thread


def main(argv=None):
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--poll-seconds', type=float, default=5)
    args = parser.parse_args(argv)
    if args.poll_seconds <= 0:
        parser.error('--poll-seconds must be positive')
    directory = args.directory or Path(os.environ.get('TRANSCRIPTS_DIR', 'runtime/transcripts'))
    if not directory.is_absolute():
        directory = ROOT / directory
    logging.basicConfig(level=logging.INFO)
    try:
        serve(directory, args.once, args.poll_seconds)
    except KeyboardInterrupt:
        return 0
    except Exception as error:
        LOG.error('Analytics worker stopped (%s); check database configuration', type(error).__name__)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
