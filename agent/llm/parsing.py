"""Separate the model's reasoning block from the answer meant for the customer."""
from __future__ import annotations

import re


class ThoughtParser:
    def __init__(self, open_tag: str, close_tag: str):
        self._pattern = re.compile(f"{re.escape(open_tag)}(.*?)(?:{re.escape(close_tag)}|$)", re.S)

    def split(self, text: str | None) -> tuple[str, str]:
        """Return (answer, thoughts). An unclosed block means everything after the open tag is a thought."""
        if not text:
            return "", ""
        thoughts = "\n".join(m.strip() for m in self._pattern.findall(text))
        answer = self._pattern.sub("", text).strip()
        return answer, thoughts
