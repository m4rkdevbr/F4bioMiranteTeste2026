"""LLM generation node (OpenRouter free chain)."""

from __future__ import annotations

import time
from typing import Any

from modernization_pipeline.services.code_sanitizer import sanitize_generated_code
from modernization_pipeline.services.llm_client import LLMGenerationError, generate_with_fallback
from modernization_pipeline.services.prompt_builder import (
    build_user_prompt,
    load_system_prompt,
    prompt_hash,
)
from modernization_pipeline.state import PipelineState


def generation_node(state: PipelineState) -> dict[str, Any]:
    started = time.perf_counter()
    timings = dict(state.get("node_timings") or {})
    errors = list(state.get("errors") or [])
    notes = list(state.get("generation_notes") or [])

    parse_errors = state.get("parse_errors") or []
    if parse_errors and not (state.get("parsed_ir") or {}).get("name"):
        timings["generation"] = round((time.perf_counter() - started) * 1000, 2)
        errors.append("Skipping generation due to critical parse errors")
        return {
            "generated_code": None,
            "generation_notes": notes + ["skipped_due_to_parse_errors"],
            "generation_meta": {"skipped": True},
            "errors": errors,
            "node_timings": timings,
        }

    system_prompt = load_system_prompt()
    user_prompt = build_user_prompt(
        source_code=state.get("source_code") or "",
        parsed_ir=state.get("parsed_ir") or {},
        semantic_profile=state.get("semantic_profile") or {},
        schema_sql=state.get("schema_sql"),
        validation_feedback=state.get("validation_results"),
    )
    p_hash = prompt_hash(system_prompt, user_prompt)

    try:
        result = generate_with_fallback(system_prompt=system_prompt, user_prompt=user_prompt)
        code = sanitize_generated_code(result["content"])
        meta = {
            "model_used": result["model_used"],
            "attempts": result["attempts"],
            "fallback_triggered": result["fallback_triggered"],
            "prompt_version": "generation_system_v1",
        }
        notes.append(f"generated_with:{result['model_used']}")
        generated = code
    except LLMGenerationError as exc:
        errors.append(str(exc))
        meta = {"attempts": exc.attempts, "failed": True}
        generated = None
        notes.append("generation_failed")

    timings["generation"] = round((time.perf_counter() - started) * 1000, 2)
    return {
        "generated_code": generated,
        "generation_prompt_hash": p_hash,
        "generation_notes": notes,
        "generation_meta": meta,
        "errors": errors,
        "node_timings": timings,
    }
