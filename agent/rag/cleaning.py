"""Step 2: clean raw text before chunking and embedding."""
from __future__ import annotations

import re
import unicodedata

_MD_EMPHASIS = re.compile(r"(\*\*|__|\*|_|`)(.+?)\1")
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACES = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _CONTROL.sub("", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _MD_EMPHASIS.sub(r"\2", text)
    lines = [_SPACES.sub(" ", line).strip() for line in text.splitlines()]
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()
