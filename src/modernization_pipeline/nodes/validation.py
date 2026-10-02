"""Validation and evaluation node."""

from __future__ import annotations

import time
from typing import Any

from modernization_pipeline.state import PipelineState
from modernization_pipeline.validation.ast_check import check_ast, check_ruff
from modernization_pipeline.validation.metrics import compute_metrics, derive_status


def validation_node(state: PipelineState) -> dict[str, Any]:
    started = time.perf_counter()
    code = state.get("generated_code")
    errors = list(state.get("errors") or [])
    had_fatal = bool(errors) and code is None

    ast_result = check_ast(code or "")
    ruff_result = check_ruff(code or "")
    validation_results = {
        "ast": ast_result,
        "ruff": ruff_result,
    }

    # One retry path is handled by graph conditional; here we only score.
    evaluation = compute_metrics(
        generated_code=code,
        semantic_profile=state.get("semantic_profile") or {},
        pipeline_ok=not had_fatal and bool(ast_result.get("ok")),
        validation_results=validation_results,
    )
    status = derive_status(
        generated_code=code,
        validation_results=validation_results,
        had_fatal_error=had_fatal,
    )

    report = {
        "run_id": state.get("run_id"),
        "procedure_name": state.get("procedure_name")
        or (state.get("parsed_ir") or {}).get("name"),
        "parsing": {
            "errors": state.get("parse_errors") or [],
            "ir_summary": {
                "kind": (state.get("parsed_ir") or {}).get("kind"),
                "name": (state.get("parsed_ir") or {}).get("name"),
                "param_count": len((state.get("parsed_ir") or {}).get("parameters") or []),
                "sql_fragment_count": len((state.get("parsed_ir") or {}).get("sql_fragments") or []),
            },
        },
        "semantic_analysis": state.get("semantic_profile") or {},
        "generation": {
            **(state.get("generation_meta") or {}),
            "prompt_hash": state.get("generation_prompt_hash"),
            "notes": state.get("generation_notes") or [],
        },
        "validation": validation_results,
        "evaluation": evaluation,
        "timings_ms": state.get("node_timings") or {},
        "errors": errors,
    }

    timings = dict(state.get("node_timings") or {})
    timings["validation"] = round((time.perf_counter() - started) * 1000, 2)
    report["timings_ms"] = timings

    return {
        "validation_results": validation_results,
        "evaluation": evaluation,
        "report": report,
        "status": status,
        "node_timings": timings,
    }
