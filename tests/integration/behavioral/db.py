"""Shared Postgres helpers for behavioral equivalence tests."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import asyncpg

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "sql" / "fixtures"
SCHEMA = "beh"


def db_url() -> str | None:
    return os.getenv("DATABASE_URL_SYNC") or os.getenv("BEHAVIORAL_DATABASE_URL")


def dsn() -> str:
    raw = db_url() or ""
    return raw.replace("postgresql+asyncpg://", "postgresql://")


async def connect() -> asyncpg.Connection:
    return await asyncpg.connect(dsn())


def _qualify_anexo_a(sql: str) -> str:
    """Rewrite Anexo A DDL to live under the isolated behavioral schema."""
    sql = sql.replace("CREATE TABLE ", f"CREATE TABLE {SCHEMA}.")
    sql = sql.replace("CREATE INDEX ", "CREATE INDEX ")
    sql = sql.replace("REFERENCES clientes(", f"REFERENCES {SCHEMA}.clientes(")
    sql = sql.replace("REFERENCES contas(", f"REFERENCES {SCHEMA}.contas(")
    # Indexes reference bare table names — qualify via ON clause.
    sql = re.sub(
        r"ON (clientes|contas|transacoes|taxas|log_auditoria)\b",
        rf"ON {SCHEMA}.\1",
        sql,
    )
    return sql


def _qualify_procedure(sql: str) -> str:
    """Install procedure into beh schema and qualify table names inside body."""
    sql = sql.replace(
        "CREATE OR REPLACE PROCEDURE sp_",
        f"CREATE OR REPLACE PROCEDURE {SCHEMA}.sp_",
    )
    for table in ("contas", "transacoes", "taxas", "log_auditoria", "clientes"):
        sql = re.sub(
            rf"\b(FROM|INTO|UPDATE|INSERT INTO|JOIN)\s+{table}\b",
            rf"\1 {SCHEMA}.{table}",
            sql,
            flags=re.IGNORECASE,
        )
    return sql


async def reset_schema(conn: asyncpg.Connection) -> None:
    await conn.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
    await conn.execute(f"CREATE SCHEMA {SCHEMA}")
    anexo_a = (FIXTURES / "anexo_a_schema.sql").read_text(encoding="utf-8")
    await conn.execute(_qualify_anexo_a(anexo_a))


async def install_procedure(conn: asyncpg.Connection, fixture_name: str) -> None:
    raw = (FIXTURES / fixture_name).read_text(encoding="utf-8")
    await conn.execute(_qualify_procedure(raw))


async def seed_client_and_accounts(
    conn: asyncpg.Connection,
    *,
    origem_saldo: str = "1000.00",
    destino_saldo: str = "100.00",
    origem_status: str = "ATIVA",
    destino_status: str = "ATIVA",
) -> tuple[int, int]:
    cliente_id = await conn.fetchval(
        f"""
        INSERT INTO {SCHEMA}.clientes (nome, cpf, status)
        VALUES ('Cliente Behavioral', '12345678901', 'ATIVO')
        RETURNING id
        """
    )
    origem_id = await conn.fetchval(
        f"""
        INSERT INTO {SCHEMA}.contas
            (cliente_id, agencia, numero, tipo, saldo, status)
        VALUES ($1, '0001', '10001', 'CORRENTE', $2::numeric, $3)
        RETURNING id
        """,
        cliente_id,
        origem_saldo,
        origem_status,
    )
    destino_id = await conn.fetchval(
        f"""
        INSERT INTO {SCHEMA}.contas
            (cliente_id, agencia, numero, tipo, saldo, status)
        VALUES ($1, '0001', '10002', 'CORRENTE', $2::numeric, $3)
        RETURNING id
        """,
        cliente_id,
        destino_saldo,
        destino_status,
    )
    return int(origem_id), int(destino_id)


async def snapshot_banking(conn: asyncpg.Connection) -> dict[str, Any]:
    contas = await conn.fetch(
        f"SELECT id, saldo::text, status FROM {SCHEMA}.contas ORDER BY id"
    )
    txs = await conn.fetch(
        f"""
        SELECT conta_origem_id, conta_destino_id, tipo, valor::text, status
          FROM {SCHEMA}.transacoes
         ORDER BY id
        """
    )
    logs = await conn.fetch(
        f"""
        SELECT entidade, entidade_id, acao, detalhes::text
          FROM {SCHEMA}.log_auditoria
         ORDER BY id
        """
    )
    return {
        "contas": [dict(r) for r in contas],
        "transacoes": [dict(r) for r in txs],
        "logs": [dict(r) for r in logs],
    }
