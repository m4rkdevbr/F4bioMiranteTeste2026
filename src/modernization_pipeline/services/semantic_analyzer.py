"""Rule-based semantic analysis over the parsed IR."""

from __future__ import annotations

from typing import Any


def _risk(
    code: str,
    severity: str,
    message: str,
    translation_hint: str,
) -> dict[str, str]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "translation_hint": translation_hint,
    }


def analyze_semantics(parsed_ir: dict[str, Any]) -> dict[str, Any]:
    constructs = parsed_ir.get("body_constructs") or {}
    cursors = parsed_ir.get("cursors") or []
    params = parsed_ir.get("parameters") or []
    nested = parsed_ir.get("nested_calls") or []
    returns = (parsed_ir.get("returns") or "").upper()

    risk_flags: list[dict[str, str]] = []
    translation_hints: list[str] = []

    if cursors or constructs.get("has_open_cursor") or constructs.get("has_fetch"):
        risk_flags.append(
            _risk(
                "cursor_loop",
                "critical",
                "Explicit cursor/loop detected; naive translation may cause N+1 queries.",
                "Prefer set-based SQL or bulk fetch + batch DML in Python.",
            )
        )
        translation_hints.append("Refactor cursor loops to set-based or bulk operations.")

    if constructs.get("has_for_update"):
        risk_flags.append(
            _risk(
                "for_update",
                "warning",
                "Row locks via FOR UPDATE require explicit transaction management.",
                "Use SQLAlchemy session.begin() and SELECT ... FOR UPDATE.",
            )
        )
        translation_hints.append("Wrap FOR UPDATE reads and writes in a single transaction.")

    if constructs.get("has_exception") or constructs.get("has_raise_exception"):
        risk_flags.append(
            _risk(
                "exception_handler",
                "warning",
                "EXCEPTION / RAISE EXCEPTION blocks must map to Python error handling.",
                "Raise domain exceptions in Python; keep audit logging side-effects.",
            )
        )
        translation_hints.append("Map RAISE EXCEPTION to typed Python exceptions.")

    if constructs.get("has_jsonb"):
        risk_flags.append(
            _risk(
                "jsonb",
                "info",
                "JSONB / jsonb_build_object usage detected.",
                "Use dict payloads and JSON/JSONB binds in SQLAlchemy.",
            )
        )

    if constructs.get("has_recursive_cte"):
        risk_flags.append(
            _risk(
                "recursive_cte",
                "critical",
                "WITH RECURSIVE CTE detected.",
                "Keep recursive CTE as parameterized SQL unless a clear Python rewrite is safer.",
            )
        )
        translation_hints.append("Preserve recursive CTE in SQL text executed from Python.")

    if constructs.get("has_return_query") or returns.startswith("TABLE"):
        risk_flags.append(
            _risk(
                "return_query",
                "warning",
                "SETOF / RETURN QUERY pattern detected.",
                "Expose an async generator or list[dict] / DataFrame-like result in Python.",
            )
        )
        translation_hints.append("Return tabular results as list[dict] or async iterator.")

    if nested:
        risk_flags.append(
            _risk(
                "nested_function_call",
                "warning",
                f"Nested function calls detected: {', '.join(nested)}.",
                "Import/call the modernized sibling module or inline when trivial.",
            )
        )
        translation_hints.append("Resolve nested calls via imports of modernized modules.")

    if constructs.get("has_raise_notice") or constructs.get("has_raise_warning"):
        risk_flags.append(
            _risk(
                "raise_notice",
                "info",
                "RAISE NOTICE/WARNING used for observability.",
                "Map to logging.getLogger(__name__).info/warning.",
            )
        )

    if constructs.get("has_get_diagnostics"):
        risk_flags.append(
            _risk(
                "get_diagnostics",
                "info",
                "GET DIAGNOSTICS ROW_COUNT usage detected.",
                "Use Result.rowcount from SQLAlchemy execution.",
            )
        )

    out_params = [p for p in params if p.get("direction") in {"OUT", "INOUT"}]
    if out_params:
        risk_flags.append(
            _risk(
                "out_parameters",
                "info",
                f"OUT/INOUT parameters: {[p['name'] for p in out_params]}.",
                "Expose as dataclass / NamedTuple / dict return value.",
            )
        )
        translation_hints.append("Return OUT parameters as a structured Python object.")

    if not risk_flags:
        translation_hints.append(
            "Simple scalar/set-based routine: Python function + parameterized SQL is preferred."
        )

    severity_rank = {"info": 1, "warning": 2, "critical": 3}
    max_severity = max((severity_rank[r["severity"]] for r in risk_flags), default=1)
    complexity = {1: "low", 2: "medium", 3: "high"}[max_severity]

    return {
        "parameters": params,
        "out_parameters": out_params,
        "variables": parsed_ir.get("variables") or [],
        "cursors": cursors,
        "constructs": constructs,
        "nested_calls": nested,
        "tables_referenced": sorted(
            {
                t
                for frag in (parsed_ir.get("sql_fragments") or [])
                for t in (frag.get("tables") or [])
            }
        ),
        "risk_flags": risk_flags,
        "translation_hints": translation_hints,
        "complexity": complexity,
        "recommended_strategy": (
            "hybrid_sql_in_python"
            if any(r["code"] in {"recursive_cte", "for_update", "cursor_loop"} for r in risk_flags)
            else "python_with_parameterized_sql"
        ),
    }
