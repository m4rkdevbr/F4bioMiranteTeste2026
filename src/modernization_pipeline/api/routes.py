"""HTTP API: POST /modernize, GET /health, GET /evaluation/summary.

Mounted by LangGraph CLI via langgraph.json → http.app.
"""

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(
    title="Modernization Pipeline",
    description="Hybrid LangGraph pipeline: PL/pgSQL → Python 3.14",
    version="1.0.0",
)


class ModernizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_code: str = Field(..., min_length=1, description="PL/pgSQL function or procedure source")
    schema_sql: str | None = Field(default=None, description="Optional DDL context (Anexo A)")
    procedure_name: str | None = Field(default=None)
    metadata: dict[str, Any] | None = Field(default=None)


class ModernizeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    generated_code: str | None
    report: dict[str, Any]
    history_id: str | None
    run_id: str | None = None


ModernizeRequest.model_rebuild()
ModernizeResponse.model_rebuild()


@app.get("/health")
async def health() -> dict[str, str]:
    from modernization_pipeline.observability.langfuse import check_langfuse

    try:
        from modernization_pipeline.persistence.database import check_postgres

        postgres = "ok" if await check_postgres() else "degraded"
    except Exception:  # noqa: BLE001
        postgres = "degraded"
    langfuse = check_langfuse()
    overall = "ok" if postgres == "ok" else "degraded"
    return {
        "status": overall,
        "postgres": postgres,
        "langfuse": langfuse,
    }


@app.post("/modernize")
async def modernize(body: ModernizeRequest) -> ModernizeResponse:
    from modernization_pipeline.graph import run_pipeline

    try:
        result = await run_pipeline(
            source_code=body.source_code,
            schema_sql=body.schema_sql,
            procedure_name=body.procedure_name,
            metadata=body.metadata,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"error": str(exc)}) from exc

    return ModernizeResponse(
        status=result.get("status") or "failure",
        generated_code=result.get("generated_code"),
        report=result.get("report") or {},
        history_id=result.get("history_id"),
        run_id=result.get("run_id"),
    )


@app.get("/evaluation/summary")
async def evaluation_summary(limit: int = 100) -> dict[str, Any]:
    from modernization_pipeline.persistence import repository
    from modernization_pipeline.persistence.database import connection_scope

    try:
        async with connection_scope() as conn:
            return await repository.evaluation_summary(conn, limit=limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"error": str(exc)}) from exc
