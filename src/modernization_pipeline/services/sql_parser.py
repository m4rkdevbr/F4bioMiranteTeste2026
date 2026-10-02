"""PL/pgSQL / SQL parsing into a structured intermediate representation."""

from __future__ import annotations

import re
from typing import Any

import sqlglot
from sqlglot import exp

_CREATE_RE = re.compile(
    r"CREATE\s+OR\s+REPLACE\s+(FUNCTION|PROCEDURE)\s+([a-zA-Z_][\w$]*)\s*\((.*?)\)\s*"
    r"(?:RETURNS\s+(TABLE\s*\(.*?\)|[^\n]+))?\s*"
    r".*?LANGUAGE\s+(\w+)\s*"
    r"AS\s+\$\$(.*)\$\$\s*;",
    re.IGNORECASE | re.DOTALL,
)

_PARAM_RE = re.compile(
    r"(?:(IN|OUT|INOUT)\s+)?([a-zA-Z_][\w$]*)\s+([A-Z][\w\s().%,]+?)(?=,|$)",
    re.IGNORECASE,
)

_DECLARE_BLOCK_RE = re.compile(
    r"DECLARE\s+(.*?)BEGIN",
    re.IGNORECASE | re.DOTALL,
)

_VAR_RE = re.compile(
    r"([a-zA-Z_][\w$]*)\s+([A-Z][\w\s().%,]+?)(?:\s*:=\s*([^;]+))?\s*;",
    re.IGNORECASE,
)

_CURSOR_RE = re.compile(
    r"([a-zA-Z_][\w$]*)\s+CURSOR\s+FOR\s+(.*?);",
    re.IGNORECASE | re.DOTALL,
)

_SQL_STMT_RE = re.compile(
    r"\b(SELECT|INSERT|UPDATE|DELETE|WITH)\b[\s\S]*?(?=;)",
    re.IGNORECASE,
)


def _normalize_ws(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


def _parse_parameters(raw: str) -> list[dict[str, str]]:
    params: list[dict[str, str]] = []
    if not raw.strip():
        return params
    for match in _PARAM_RE.finditer(raw):
        direction = (match.group(1) or "IN").upper()
        name = match.group(2)
        typ = _normalize_ws(match.group(3))
        params.append({"name": name, "direction": direction, "type": typ})
    return params


def _parse_declarations(body: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    variables: list[dict[str, Any]] = []
    cursors: list[dict[str, Any]] = []
    decl = _DECLARE_BLOCK_RE.search(body)
    if not decl:
        return variables, cursors
    block = decl.group(1)
    for cur in _CURSOR_RE.finditer(block):
        cursors.append(
            {
                "name": cur.group(1),
                "query": _normalize_ws(cur.group(2)),
            }
        )
    cleaned = _CURSOR_RE.sub("", block)
    for var in _VAR_RE.finditer(cleaned):
        variables.append(
            {
                "name": var.group(1),
                "type": _normalize_ws(var.group(2)),
                "default": _normalize_ws(var.group(3)) if var.group(3) else None,
            }
        )
    return variables, cursors


def _extract_sql_fragments(body: str) -> list[dict[str, Any]]:
    fragments: list[dict[str, Any]] = []
    for match in _SQL_STMT_RE.finditer(body):
        sql_text = match.group(0).strip()
        if len(sql_text) < 8:
            continue
        entry: dict[str, Any] = {
            "sql": sql_text,
            "kind": match.group(1).upper(),
            "tables": [],
            "parse_ok": False,
            "error": None,
        }
        try:
            parsed = sqlglot.parse_one(sql_text, read="postgres")
            entry["parse_ok"] = True
            entry["tables"] = sorted(
                {t.name for t in parsed.find_all(exp.Table) if getattr(t, "name", None)}
            )
            entry["ast_type"] = type(parsed).__name__
        except Exception as exc:  # noqa: BLE001 - collect parse failures into IR
            entry["error"] = str(exc)
        fragments.append(entry)
    return fragments


def _detect_body_constructs(body: str) -> dict[str, bool]:
    upper = body.upper()
    return {
        "has_exception": "EXCEPTION" in upper,
        "has_raise_exception": "RAISE EXCEPTION" in upper,
        "has_raise_notice": "RAISE NOTICE" in upper,
        "has_raise_warning": "RAISE WARNING" in upper,
        "has_for_update": "FOR UPDATE" in upper,
        "has_get_diagnostics": "GET DIAGNOSTICS" in upper,
        "has_loop": bool(re.search(r"\bLOOP\b", upper)),
        "has_open_cursor": bool(re.search(r"\bOPEN\b", upper)),
        "has_fetch": bool(re.search(r"\bFETCH\b", upper)),
        "has_return_query": "RETURN QUERY" in upper,
        "has_recursive_cte": bool(re.search(r"WITH\s+RECURSIVE", upper)),
        "has_jsonb": "JSONB" in upper or "jsonb_build_object" in body.lower(),
        "has_case": bool(re.search(r"\bCASE\b", upper)),
        "has_transaction_keywords": any(
            k in upper for k in ("BEGIN", "COMMIT", "ROLLBACK")
        ),
    }


def _nested_function_calls(body: str, self_name: str | None) -> list[str]:
    calls = re.findall(r"\b([a-zA-Z_][\w$]*)\s*\(", body)
    ignore = {
        "coalesce",
        "sum",
        "count",
        "greatest",
        "least",
        "now",
        "date_trunc",
        "jsonb_build_object",
        "upper",
        "lower",
        "length",
        "trim",
        "if",
        "case",
        "when",
        "select",
        "insert",
        "update",
        "delete",
        "values",
        "exists",
        "not",
        "and",
        "or",
    }
    result: list[str] = []
    for name in calls:
        low = name.lower()
        if low in ignore:
            continue
        if self_name and low == self_name.lower():
            continue
        if low.startswith(("v_", "p_", "cur_")):
            continue
        if low not in result:
            result.append(low)
    return result


def parse_plpgsql(source_code: str) -> dict[str, Any]:
    """Parse a PL/pgSQL function/procedure into a serializable IR."""
    errors: list[str] = []
    text = source_code.strip()
    match = _CREATE_RE.search(text)
    if not match:
        errors.append("Could not match CREATE FUNCTION/PROCEDURE ... AS $$ ... $$ pattern")
        return {
            "kind": "unknown",
            "name": None,
            "language": None,
            "parameters": [],
            "returns": None,
            "variables": [],
            "cursors": [],
            "body": text,
            "body_constructs": _detect_body_constructs(text),
            "sql_fragments": _extract_sql_fragments(text),
            "nested_calls": _nested_function_calls(text, None),
            "errors": errors,
        }

    kind = match.group(1).lower()
    name = match.group(2)
    params_raw = match.group(3) or ""
    returns = _normalize_ws(match.group(4)) if match.group(4) else None
    language = match.group(5).lower()
    body = match.group(6).strip()

    variables, cursors = _parse_declarations(body)
    constructs = _detect_body_constructs(body)
    fragments = _extract_sql_fragments(body)
    nested = _nested_function_calls(body, name)

    return {
        "kind": kind,
        "name": name,
        "language": language,
        "parameters": _parse_parameters(params_raw),
        "returns": returns,
        "variables": variables,
        "cursors": cursors,
        "body": body,
        "body_constructs": constructs,
        "sql_fragments": fragments,
        "nested_calls": nested,
        "errors": errors,
        "source_sha_preview": text[:120],
    }
