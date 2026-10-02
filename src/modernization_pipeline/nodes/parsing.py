"""Parsing node."""

from __future__ import annotations

import time
from typing import Any

from modernization_pipeline.services.sql_parser import parse_plpgsql
from modernization_pipeline.state import PipelineState


def parsing_node(state: PipelineState) -> dict[str, Any]:
    started = time.perf_counter()
    source = state.get("source_code") or ""
    parsed = parse_plpgsql(source)
    errors = list(parsed.get("errors") or [])
    timings = dict(state.get("node_timings") or {})
    timings["parsing"] = round((time.perf_counter() - started) * 1000, 2)
    return {
        "parsed_ir": parsed,
        "parse_errors": errors,
        "node_timings": timings,
        "procedure_name": state.get("procedure_name") or parsed.get("name"),
    }
