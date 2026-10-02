"""Typed LangGraph state for the modernization pipeline."""

from __future__ import annotations

from typing import Any, TypedDict


class PipelineState(TypedDict, total=False):
    # Input
    source_code: str
    schema_sql: str | None
    procedure_name: str | None
    metadata: dict[str, Any]

    # Control
    run_id: str
    retry_count: int
    node_timings: dict[str, float]
    errors: list[str]

    # Parsing
    parsed_ir: dict[str, Any]
    parse_errors: list[str]

    # Semantic analysis
    semantic_profile: dict[str, Any]

    # Generation
    generation_prompt_hash: str
    generated_code: str | None
    generation_notes: list[str]
    generation_meta: dict[str, Any]

    # Validation / evaluation
    validation_results: dict[str, Any]
    evaluation: dict[str, Any]

    # Output
    report: dict[str, Any]
    status: str  # success | failure | partial
    history_id: str | None
