"""Behavioral equivalence for Anexo D: legacy PL/pgSQL vs modernized asyncpg."""

from __future__ import annotations

from decimal import Decimal

import asyncpg
import pytest

from .behavioral.db import (
    FIXTURES,
    SCHEMA,
    connect,
    db_url,
    install_procedure,
    reset_schema,
    seed_client_and_accounts,
    snapshot_banking,
)
from .behavioral.modern_d import TransferError, transferir_entre_contas

pytestmark = pytest.mark.skipif(not db_url(), reason="DATABASE_URL_SYNC not configured")


async def _run_legacy_transfer(conn, origem: int, destino: int, valor: Decimal) -> None:
    await conn.execute(
        f"CALL {SCHEMA}.sp_transferir_entre_contas($1, $2, $3)",
        origem,
        destino,
        valor,
    )


@pytest.mark.asyncio
async def test_anexo_d_success_parity_legacy_vs_modern():
    """Happy path: same balances, TRANSFERENCIA row and TRANSFERENCIA_OK log."""
    conn = await connect()
    try:
        await reset_schema(conn)
        await install_procedure(conn, "anexo_d_sp_transferir_entre_contas.sql")

        # --- Legacy ---
        o1, d1 = await seed_client_and_accounts(
            conn, origem_saldo="1000.00", destino_saldo="100.00"
        )
        await _run_legacy_transfer(conn, o1, d1, Decimal("250.50"))
        snap_legacy = await snapshot_banking(conn)

        # --- Modern (fresh seed, same amounts) ---
        await reset_schema(conn)
        await install_procedure(conn, "anexo_d_sp_transferir_entre_contas.sql")
        o2, d2 = await seed_client_and_accounts(
            conn, origem_saldo="1000.00", destino_saldo="100.00"
        )
        await transferir_entre_contas(conn, o2, d2, Decimal("250.50"))
        snap_modern = await snapshot_banking(conn)

        assert snap_legacy["contas"][0]["saldo"] == "749.50"
        assert snap_legacy["contas"][1]["saldo"] == "350.50"
        assert snap_modern["contas"][0]["saldo"] == snap_legacy["contas"][0]["saldo"]
        assert snap_modern["contas"][1]["saldo"] == snap_legacy["contas"][1]["saldo"]

        assert len(snap_legacy["transacoes"]) == 1
        assert len(snap_modern["transacoes"]) == 1
        assert snap_legacy["transacoes"][0]["tipo"] == "TRANSFERENCIA"
        assert snap_modern["transacoes"][0]["tipo"] == "TRANSFERENCIA"
        assert snap_legacy["transacoes"][0]["valor"] == snap_modern["transacoes"][0]["valor"]

        assert any(row["acao"] == "TRANSFERENCIA_OK" for row in snap_legacy["logs"])
        assert any(row["acao"] == "TRANSFERENCIA_OK" for row in snap_modern["logs"])
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_anexo_d_insufficient_funds_rollback_parity():
    """Both paths raise and leave balances unchanged."""
    conn = await connect()
    try:
        await reset_schema(conn)
        await install_procedure(conn, "anexo_d_sp_transferir_entre_contas.sql")
        origem, destino = await seed_client_and_accounts(
            conn, origem_saldo="50.00", destino_saldo="10.00"
        )
        before = await snapshot_banking(conn)

        with pytest.raises(asyncpg.RaiseError):
            await _run_legacy_transfer(conn, origem, destino, Decimal("999.00"))
        after_legacy = await snapshot_banking(conn)
        assert after_legacy["contas"] == before["contas"]
        assert after_legacy["transacoes"] == before["transacoes"]

        with pytest.raises(TransferError):
            await transferir_entre_contas(conn, origem, destino, Decimal("999.00"))
        after_modern = await snapshot_banking(conn)
        assert after_modern["contas"] == before["contas"]
        assert after_modern["transacoes"] == before["transacoes"]
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_anexo_d_inactive_account_parity():
    conn = await connect()
    try:
        await reset_schema(conn)
        await install_procedure(conn, "anexo_d_sp_transferir_entre_contas.sql")
        origem, destino = await seed_client_and_accounts(
            conn,
            origem_saldo="500.00",
            destino_saldo="100.00",
            destino_status="INATIVA",
        )
        before = await snapshot_banking(conn)

        with pytest.raises(asyncpg.RaiseError):
            await _run_legacy_transfer(conn, origem, destino, Decimal("10.00"))
        with pytest.raises(TransferError):
            await transferir_entre_contas(conn, origem, destino, Decimal("10.00"))

        after = await snapshot_banking(conn)
        assert after["contas"] == before["contas"]
    finally:
        await conn.close()


def test_anexo_d_fixture_exists():
    assert (FIXTURES / "anexo_d_sp_transferir_entre_contas.sql").exists()
