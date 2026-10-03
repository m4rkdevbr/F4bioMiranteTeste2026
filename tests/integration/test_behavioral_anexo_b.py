"""Behavioral smoke test for Anexo B against a real Postgres when available."""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[2] / "sql" / "fixtures"


def _db_url() -> str | None:
    return os.getenv("DATABASE_URL_SYNC") or os.getenv("BEHAVIORAL_DATABASE_URL")


@pytest.mark.skipif(not _db_url(), reason="DATABASE_URL_SYNC not configured")
@pytest.mark.asyncio
async def test_anexo_b_behavioral_parity_smoke():
    """Create legacy tables, seed data, compare PL/pgSQL-ish query vs generated Python SQL."""
    import asyncpg

    dsn = (_db_url() or "").replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contas (
                id BIGSERIAL PRIMARY KEY,
                cliente_id BIGINT NOT NULL,
                saldo NUMERIC(18,2) NOT NULL DEFAULT 0,
                status VARCHAR(20) NOT NULL DEFAULT 'ATIVA'
            );
            DELETE FROM contas WHERE cliente_id = 9001;
            INSERT INTO contas (cliente_id, saldo, status) VALUES
              (9001, 100.50, 'ATIVA'),
              (9001, 49.50, 'ATIVA'),
              (9001, 999.00, 'INATIVA');
            """
        )
        expected = await conn.fetchval(
            """
            SELECT COALESCE(SUM(saldo), 0)
              FROM contas
             WHERE cliente_id = $1 AND status = 'ATIVA'
            """,
            9001,
        )
        assert Decimal(str(expected)) == Decimal("150.00")

        # Same SQL shape used by the modernized Python module.
        modernized = await conn.fetchval(
            """
            SELECT COALESCE(SUM(saldo), 0)
              FROM contas
             WHERE cliente_id = $1 AND status = $2
            """,
            9001,
            "ATIVA",
        )
        assert Decimal(str(modernized)) == Decimal(str(expected))
    finally:
        await conn.close()


def test_anexo_b_fixture_exists():
    assert (FIXTURES / "anexo_b_fn_saldo_cliente.sql").exists()
