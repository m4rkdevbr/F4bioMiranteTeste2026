"""Automatic evaluation metrics for modernization quality."""

from __future__ import annotations

from typing import Any

from modernization_pipeline.validation.ast_check import check_ast, check_ruff


def _risk_addressed(code: str, risk_code: str) -> bool:
    low = code.lower()
    mapping: dict[str, list[str]] = {
        "cursor_loop": ["fetchall", "executemany", "bulk", "for row in", "select "],
        "for_update": ["for update", "begin()", "session.begin", "transaction"],
        "exception_handler": ["except", "raise ", "try:"],
        "jsonb": ["json", "jsonb", "dict"],
        "recursive_cte": ["with recursive", "recursive"],
        "return_query": ["list[", "async iterator", "yield", "return ["],
        "nested_function_call": ["import ", "from "],
        "raise_notice": ["logging", "logger.", "getlogger"],
        "get_diagnostics": ["rowcount"],
        "out_parameters": ["dataclass", "typeddict", "namedtuple", "return {", "return ("],
    }
    needles = mapping.get(risk_code, [])
    return any(n in low for n in needles) if needles else True


def compute_metrics(
    *,
    generated_code: str | None,
    semantic_profile: dict[str, Any],
    pipeline_ok: bool,
    validation_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    code = generated_code or ""
    ast_result = (validation_results or {}).get("ast") or check_ast(code)
    ruff_result = (validation_results or {}).get("ruff") or check_ruff(code)

    risks = semantic_profile.get("risk_flags") or []
    addressed = 0
    details_flags: list[dict[str, Any]] = []
    for risk in risks:
        code_name = risk.get("code", "")
        ok = _risk_addressed(code, code_name)
        details_flags.append({"code": code_name, "addressed": ok})
        if ok:
            addressed += 1

    structural = (addressed / len(risks)) if risks else (1.0 if ast_result.get("ok") else 0.0)
    loc = len([ln for ln in code.splitlines() if ln.strip() and not ln.strip().startswith("#")])

    scores = {
        "ast_parse_success": 1.0 if ast_result.get("ok") else 0.0,
        "pipeline_completion": 1.0 if pipeline_ok else 0.0,
        "structural_mapping_score": round(float(structural), 4),
        "generated_loc": float(loc),
        "ruff_clean": 1.0 if ruff_result.get("ok") else 0.0,
    }

    return {
        "scores": scores,
        "details": {
            "risk_coverage": details_flags,
            "ast": ast_result,
            "ruff_issue_count": len(ruff_result.get("issues") or []),
        },
    }


def derive_status(
    *,
    generated_code: str | None,
    validation_results: dict[str, Any],
    had_fatal_error: bool,
) -> str:
    if had_fatal_error or not generated_code:
        return "failure"
    ast_ok = bool((validation_results.get("ast") or {}).get("ok"))
    if not ast_ok:
        return "failure"
    ruff_ok = bool((validation_results.get("ruff") or {}).get("ok", True))
    if not ruff_ok:
        return "partial"
    return "success"
