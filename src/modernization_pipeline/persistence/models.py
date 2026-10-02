"""ORM models retained as documentation of the relational schema.

Runtime persistence uses asyncpg (see repository.py / database.py).
"""

from __future__ import annotations

# Schema source of truth: sql/init/01_schema.sql
SCHEMA_TABLES = (
    "modernization_history",
    "pipeline_evaluation_scores",
)
