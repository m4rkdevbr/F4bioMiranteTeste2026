"""Strip markdown fences and normalize LLM code output."""

from __future__ import annotations

import re

_FENCE_RE = re.compile(
    r"^\s*```(?:python|py)?\s*\n([\s\S]*?)\n```\s*$",
    re.IGNORECASE,
)

_INLINE_FENCE_RE = re.compile(r"```(?:python|py)?\s*\n([\s\S]*?)```", re.IGNORECASE)


def sanitize_generated_code(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""

    match = _FENCE_RE.match(text)
    if match:
        return match.group(1).strip() + "\n"

    # Model sometimes wraps explanation + fence
    inline = _INLINE_FENCE_RE.search(text)
    if inline:
        return inline.group(1).strip() + "\n"

    # Drop common leading chatter lines
    lines = text.splitlines()
    while lines and lines[0].strip().lower().startswith(
        ("sure", "here", "below", "this python", "the following")
    ):
        lines.pop(0)
    return "\n".join(lines).strip() + "\n"
