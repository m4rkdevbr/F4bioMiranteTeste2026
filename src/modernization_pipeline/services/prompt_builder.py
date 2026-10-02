"""Build LLM prompts from parsed IR + semantic profile (never raw-only)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "generation_system_v1.txt"

DEFAULT_SYSTEM_PROMPT = """You are a senior engineer modernizing PostgreSQL PL/pgSQL into Python 3.14.

You receive a structured intermediate representation (IR), a semantic profile with risk flags,
optional schema DDL, and translation hints. Do NOT invent business rules that are absent.

Architectural rules:
1. Prefer Python + parameterized SQL (SQLAlchemy 2 Core / text()) for set-based logic.
2. For FOR UPDATE / multi-statement transactions: use a single explicit transaction.
3. For cursors/loops: avoid N+1; prefer set-based SQL or bulk fetch + batch writes.
4. For WITH RECURSIVE / complex RETURN QUERY: keep SQL in parameterized strings.
5. Map RAISE EXCEPTION to Python exceptions; RAISE NOTICE to logging.
6. OUT parameters become dataclass / TypedDict / dict returns.
7. Nested function calls become imports/calls to sibling modernized modules when named.

Output requirements:
- Return ONLY valid Python 3.14 module source code.
- No markdown fences, no commentary before/after the code.
- Include type hints, module docstring in Brazilian Portuguese (short), and logging where notices existed.
- Use sqlalchemy / sqlalchemy.ext.asyncio style suitable for async services when DB I/O is needed.
"""


def load_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.exists():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return DEFAULT_SYSTEM_PROMPT


def build_user_prompt(
    *,
    source_code: str,
    parsed_ir: dict[str, Any],
    semantic_profile: dict[str, Any],
    schema_sql: str | None = None,
    validation_feedback: dict[str, Any] | None = None,
) -> str:
    payload = {
        "task": "Translate the PL/pgSQL routine described below into a Python 3.14 module.",
        "parsed_ir": {
            "kind": parsed_ir.get("kind"),
            "name": parsed_ir.get("name"),
            "language": parsed_ir.get("language"),
            "parameters": parsed_ir.get("parameters"),
            "returns": parsed_ir.get("returns"),
            "variables": parsed_ir.get("variables"),
            "cursors": parsed_ir.get("cursors"),
            "body_constructs": parsed_ir.get("body_constructs"),
            "sql_fragments": parsed_ir.get("sql_fragments"),
            "nested_calls": parsed_ir.get("nested_calls"),
            "body": parsed_ir.get("body"),
        },
        "semantic_profile": {
            "risk_flags": semantic_profile.get("risk_flags"),
            "translation_hints": semantic_profile.get("translation_hints"),
            "recommended_strategy": semantic_profile.get("recommended_strategy"),
            "complexity": semantic_profile.get("complexity"),
            "tables_referenced": semantic_profile.get("tables_referenced"),
        },
        "schema_sql": schema_sql,
        "source_code": source_code,
        "validation_feedback": validation_feedback,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def prompt_hash(system_prompt: str, user_prompt: str) -> str:
    digest = hashlib.sha256()
    digest.update(system_prompt.encode("utf-8"))
    digest.update(b"\n---\n")
    digest.update(user_prompt.encode("utf-8"))
    return digest.hexdigest()[:16]
