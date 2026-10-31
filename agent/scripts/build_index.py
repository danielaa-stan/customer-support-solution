"""Build the RAG index from data/policies and data/cases.json.

Run from the repo root:   python -m agent.scripts.build_index
Offline fallback:         RAG_EMBEDDING_PROVIDER=tfidf python -m agent.scripts.build_index
"""
from __future__ import annotations

import logging
import sys

from agent.logging_config import setup_logging
from agent.rag.pipeline import build_index
from agent.settings import load_settings

logger = logging.getLogger("build_index")


def main() -> int:
    settings = load_settings()
    setup_logging(settings.logging)
    index = build_index(settings)
    logger.info("Done: %s", index.manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
