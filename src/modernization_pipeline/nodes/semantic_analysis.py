"""Semantic analysis node."""

from __future__ import annotations

import time
from typing import Any

from modernization_pipeline.services.semantic_analyzer import analyze_semantics
from modernization_pipeline.state import PipelineState


def semantic_analysis_node(state: PipelineState) -> dict[str, Any]:
    started = time.perf_counter()
    parsed = state.get("parsed_ir") or {}
    profile = analyze_semantics(parsed)
    timings = dict(state.get("node_timings") or {})
    timings["semantic_analysis"] = round((time.perf_counter() - started) * 1000, 2)
    return {
        "semantic_profile": profile,
        "node_timings": timings,
    }
