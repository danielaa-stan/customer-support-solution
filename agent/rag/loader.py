"""Step 1: load raw documents (contracts/05-knowledge-base-format.md)."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from agent.rag.models import PolicySection

logger = logging.getLogger(__name__)

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
_SECTION = re.compile(r"^##\s+(\d+(?:\.\d+)*)\s+(.+)$", re.M)
REQUIRED_META = ("doc_id", "title", "version")
REQUIRED_CASE_FIELDS = ("case_id", "title", "intent", "reason", "customer_message", "summary", "resolution")


def parse_front_matter(text: str) -> tuple[dict, str]:
    m = _FRONT_MATTER.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip().strip('"\'')
    return meta, text[m.end():]


def load_policy_file(path: Path) -> list[PolicySection]:
    meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_META if k not in meta]
    if missing:
        raise ValueError(f"{path.name}: front matter is missing {missing}")
    if meta["doc_id"] != path.stem:
        logger.warning("%s: doc_id '%s' does not match the file name", path.name, meta["doc_id"])

    heads = list(_SECTION.finditer(body))
    if not heads:
        raise ValueError(f"{path.name}: no '## <number> <title>' sections found")
    sections = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        sections.append(PolicySection(doc_id=meta["doc_id"], doc_title=meta["title"], version=meta["version"],
                                      section=h.group(1), title=h.group(2).strip(), text=body[h.end():end]))
    return sections


def load_policies(policies_dir: Path) -> list[PolicySection]:
    files = sorted(policies_dir.glob("*.md"))
    if not files:
        raise FileNotFoundError(f"No policy files in {policies_dir}")
    sections = [s for f in files for s in load_policy_file(f)]
    logger.info("Loaded %d policy sections from %d files", len(sections), len(files))
    return sections


def load_cases(cases_file: Path) -> list[dict]:
    cases = json.loads(cases_file.read_text(encoding="utf-8"))
    bad = [c.get("case_id", i) for i, c in enumerate(cases) if any(f not in c for f in REQUIRED_CASE_FIELDS)]
    if bad:
        raise ValueError(f"{cases_file.name}: cases missing required fields: {bad[:5]}")
    logger.info("Loaded %d cases", len(cases))
    return cases
