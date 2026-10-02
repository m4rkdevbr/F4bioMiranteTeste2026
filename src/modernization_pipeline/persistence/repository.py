"""Persistence repository using asyncpg."""

from __future__ import annotations

import json
import uuid
from typing import Any

import asyncpg


async def insert_history(
    conn: asyncpg.Connection,
    *,
    source_code: str,
    generated_code: str | None,
    report: dict[str, Any],
    status: str,
) -> uuid.UUID:
    history_id = uuid.uuid4()
    await conn.execute(
        """
        INSERT INTO modernization_history (id, source_code, generated_code, report, status)
        VALUES ($1, $2, $3, $4::jsonb, $5)
        """,
        history_id,
        source_code,
        generated_code,
        json.dumps(report),
        status,
    )
    return history_id


async def insert_evaluation_scores(
    conn: asyncpg.Connection,
    *,
    history_id: uuid.UUID | None,
    scores: dict[str, float],
    details: dict[str, Any] | None = None,
) -> None:
    for name, value in scores.items():
        await conn.execute(
            """
            INSERT INTO pipeline_evaluation_scores
                (id, history_id, metric_name, metric_value, details)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            """,
            uuid.uuid4(),
            history_id,
            name,
            value,
            json.dumps(details) if details is not None else None,
        )


async def evaluation_summary(
    conn: asyncpg.Connection,
    *,
    limit: int = 100,
) -> dict[str, Any]:
    rows = await conn.fetch(
        """
        SELECT metric_name, metric_value
          FROM pipeline_evaluation_scores
         ORDER BY created_at DESC
         LIMIT $1
        """,
        limit,
    )
    by_metric: dict[str, list[float]] = {}
    for row in rows:
        by_metric.setdefault(row["metric_name"], []).append(float(row["metric_value"]))
    averages = {
        name: (sum(values) / len(values)) if values else 0.0
        for name, values in by_metric.items()
    }
    return {
        "sample_size": len(rows),
        "metrics": averages,
        "raw_count_by_metric": {k: len(v) for k, v in by_metric.items()},
    }
