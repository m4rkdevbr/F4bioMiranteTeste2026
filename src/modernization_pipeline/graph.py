"""LangGraph modernization pipeline graph."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Literal, cast

from langgraph.graph import END, START, StateGraph

from modernization_pipeline.nodes.generation import generation_node
from modernization_pipeline.nodes.parsing import parsing_node
from modernization_pipeline.nodes.semantic_analysis import semantic_analysis_node
from modernization_pipeline.nodes.validation import validation_node
from modernization_pipeline.observability.langfuse import get_langchain_handler, score_run
from modernization_pipeline.state import PipelineState

logger = logging.getLogger(__name__)

_compiled = None


def _should_retry(state: PipelineState) -> Literal["generation", "persist"]:
    """Retry generation once when AST validation fails."""
    retry_count = int(state.get("retry_count") or 0)
    validation = state.get("validation_results") or {}
    ast_ok = bool((validation.get("ast") or {}).get("ok"))
    has_code = bool(state.get("generated_code"))
    if has_code and not ast_ok and retry_count < 1:
        return "generation"
    return "persist"


def _bump_retry(state: PipelineState) -> dict[str, Any]:
    return {"retry_count": int(state.get("retry_count") or 0) + 1}


async def _persist_node(state: PipelineState) -> dict[str, Any]:
    status = state.get("status") or "failure"
    report = dict(state.get("report") or {})
    history_id = None
    try:
        from modernization_pipeline.persistence import repository
        from modernization_pipeline.persistence.database import connection_scope

        async with connection_scope() as conn:
            row_id = await repository.insert_history(
                conn,
                source_code=state.get("source_code") or "",
                generated_code=state.get("generated_code"),
                report=report,
                status=status,
            )
            history_id = str(row_id)
            scores = ((state.get("evaluation") or {}).get("scores")) or {}
            if scores:
                await repository.insert_evaluation_scores(
                    conn,
                    history_id=row_id,
                    scores=scores,
                    details=(state.get("evaluation") or {}).get("details"),
                )
    except Exception as exc:  # noqa: BLE001 - persistence must not hide pipeline result
        logger.exception("Failed to persist modernization history: %s", exc)
        report["persistence_error"] = str(exc)
        return {"history_id": None, "report": report}

    return {"history_id": history_id, "report": report}


def build_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("parsing", parsing_node)
    graph.add_node("semantic_analysis", semantic_analysis_node)
    graph.add_node("generation", generation_node)
    graph.add_node("validation", validation_node)
    graph.add_node("bump_retry", _bump_retry)
    graph.add_node("persist", _persist_node)

    graph.add_edge(START, "parsing")
    graph.add_edge("parsing", "semantic_analysis")
    graph.add_edge("semantic_analysis", "generation")
    graph.add_edge("generation", "validation")
    graph.add_conditional_edges(
        "validation",
        _should_retry,
        {
            "generation": "bump_retry",
            "persist": "persist",
        },
    )
    graph.add_edge("bump_retry", "generation")
    graph.add_edge("persist", END)
    return graph.compile()


def get_compiled_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled


def initial_state(
    *,
    source_code: str,
    schema_sql: str | None = None,
    procedure_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> PipelineState:
    return {
        "source_code": source_code,
        "schema_sql": schema_sql,
        "procedure_name": procedure_name,
        "metadata": metadata or {},
        "run_id": str(uuid.uuid4()),
        "retry_count": 0,
        "node_timings": {},
        "errors": [],
        "parse_errors": [],
        "generation_notes": [],
    }


async def run_pipeline(
    *,
    source_code: str,
    schema_sql: str | None = None,
    procedure_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> PipelineState:
    graph = get_compiled_graph()
    state = initial_state(
        source_code=source_code,
        schema_sql=schema_sql,
        procedure_name=procedure_name,
        metadata=metadata,
    )
    config: dict[str, Any] = {"configurable": {"thread_id": state["run_id"]}}
    handler = get_langchain_handler()
    if handler is not None:
        config["callbacks"] = [handler]

    result = await graph.ainvoke(state, config=config)

    scores = ((result.get("evaluation") or {}).get("scores")) or {}
    if scores and handler is not None:
        trace_id = getattr(handler, "last_trace_id", None) or getattr(handler, "trace_id", None)
        score_run(trace_id=trace_id, scores=scores, comment="pipeline_evaluation")

    return cast(PipelineState, result)


# LangGraph CLI / durable export
graph = build_graph()
