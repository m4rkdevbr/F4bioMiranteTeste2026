"""Behavioral equivalence for Anexo C: legacy PL/pgSQL vs modernized asyncpg."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from .behavioral.db import (
    FIXTURES,
    SCHEMA,
    connect,
    db_url,
    install_procedure,
    reset_schema,
    snapshot_banking,
)
from .behavioral.modern_c import InativacaoError, atualizar_status_contas_inativas

pytestmark = pytest.mark.skipif(not db_url(), reason="DATABASE_URL_SYNC not configured")


async def _seed_inativacao(conn) -> dict[str, int]:
    """Three ATIVA accounts: recent activity, stale activity, never moved."""
    cliente_id = await conn.fetchval(
        f"""
        INSERT INTO {SCHEMA}.clientes (nome, cpf, status)
        VALUES ('Cliente Inativacao', '22345678901', 'ATIVO')
        RETURNING id
        """
    )
    recent_id = await conn.fetchval(
        f"""
        INSERT INTO {SCHEMA}.contas
            (cliente_id, agencia, numero, tipo, saldo, status)
        VALUES ($1, '0001', '20001', 'CORRENTE', 100.00, 'ATIVA')
        RETURNING id
        """,
        cliente_id,
    )
    stale_id = await conn.fetchval(
        f"""
        INSERT INTO {SCHEMA}.contas
            (cliente_id, agencia, numero, tipo, saldo, status)
        VALUES ($1, '0001', '20002', 'CORRENTE', 200.00, 'ATIVA')
        RETURNING id
        """,
        cliente_id,
    )
    never_id = await conn.fetchval(
        f"""
        INSERT INTO {SCHEMA}.contas
            (cliente_id, agencia, numero, tipo, saldo, status)
        VALUES ($1, '0001', '20003', 'CORRENTE', 300.00, 'ATIVA')
        RETURNING id
        """,
        cliente_id,
    )
    already_id = await conn.fetchval(
        f"""
        INSERT INTO {SCHEMA}.contas
            (cliente_id, agencia, numero, tipo, saldo, status)
        VALUES ($1, '0001', '20004', 'POUPANCA', 50.00, 'INATIVA')
        RETURNING id
        """,
        cliente_id,
    )

    now = datetime.now(UTC).replace(tzinfo=None)
    await conn.execute(
        f"""
        INSERT INTO {SCHEMA}.transacoes
            (conta_origem_id, tipo, valor, data_transacao, status)
        VALUES
            ($1, 'SAQUE', 10.00, $3, 'EFETIVADA'),
            ($2, 'SAQUE', 10.00, $4, 'EFETIVADA')
        """,
        recent_id,
        stale_id,
        now - timedelta(days=5),
        now - timedelta(days=60),
    )
    return {
        "recent": int(recent_id),
        "stale": int(stale_id),
        "never": int(never_id),
        "already": int(already_id),
    }


async def _run_legacy(conn, dias: int) -> None:
    # NULL placeholder for OUT p_afetadas — side effects + audit log carry the count.
    await conn.execute(
        f"CALL {SCHEMA}.sp_atualizar_status_contas_inativas($1, NULL)",
        dias,
    )


def _status_map(snap: dict) -> dict[int, str]:
    return {int(c["id"]): c["status"] for c in snap["contas"]}


@pytest.mark.asyncio
async def test_anexo_c_inativacao_parity_legacy_vs_modern():
    """Stale/never-moved ATIVA accounts become INATIVA; recent stays ATIVA."""
    conn = await connect()
    try:
        await reset_schema(conn)
        await install_procedure(conn, "anexo_c_sp_atualizar_status_contas_inativas.sql")
        ids = await _seed_inativacao(conn)
        await _run_legacy(conn, 30)
        snap_legacy = await snapshot_banking(conn)

        await reset_schema(conn)
        await install_procedure(conn, "anexo_c_sp_atualizar_status_contas_inativas.sql")
        ids_m = await _seed_inativacao(conn)
        afetadas = await atualizar_status_contas_inativas(conn, 30)
        snap_modern = await snapshot_banking(conn)

        assert afetadas == 2
        legacy = _status_map(snap_legacy)
        modern = _status_map(snap_modern)

        assert legacy[ids["recent"]] == modern[ids_m["recent"]] == "ATIVA"
        assert legacy[ids["stale"]] == modern[ids_m["stale"]] == "INATIVA"
        assert legacy[ids["never"]] == modern[ids_m["never"]] == "INATIVA"
        assert legacy[ids["already"]] == modern[ids_m["already"]] == "INATIVA"

        legacy_logs = [r for r in snap_legacy["logs"] if r["acao"] == "INATIVACAO_LOTE"]
        modern_logs = [r for r in snap_modern["logs"] if r["acao"] == "INATIVACAO_LOTE"]
        assert len(legacy_logs) == len(modern_logs) == 1
        assert '"afetadas":2' in legacy_logs[0]["detalhes"].replace(" ", "")
        assert '"afetadas":2' in modern_logs[0]["detalhes"].replace(" ", "")
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_anexo_c_invalid_dias_parity():
    conn = await connect()
    try:
        await reset_schema(conn)
        await install_procedure(conn, "anexo_c_sp_atualizar_status_contas_inativas.sql")
        await _seed_inativacao(conn)
        before = await snapshot_banking(conn)

        with pytest.raises(asyncpg.RaiseError):
            await _run_legacy(conn, 0)
        with pytest.raises(InativacaoError):
            await atualizar_status_contas_inativas(conn, 0)

        after = await snapshot_banking(conn)
        assert after["contas"] == before["contas"]
        assert after["logs"] == before["logs"]
    finally:
        await conn.close()


def test_anexo_c_fixture_exists():
    assert (FIXTURES / "anexo_c_sp_atualizar_status_contas_inativas.sql").exists()
