"""Behavioral equivalence for Anexo E: cursor PL/pgSQL vs set-based modern path."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

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
from .behavioral.modern_e import processar_lote_taxas

pytestmark = pytest.mark.skipif(not db_url(), reason="DATABASE_URL_SYNC not configured")

REF_DATE = date(2024, 6, 15)


async def _seed_lote(conn) -> tuple[int, int]:
    origem, destino = await seed_client_and_accounts(
        conn, origem_saldo="5000.00", destino_saldo="1000.00"
    )
    await conn.execute(
        f"""
        INSERT INTO {SCHEMA}.taxas
            (tipo_operacao, percentual, valor_minimo, vigente_de, vigente_ate)
        VALUES
            ('TRANSFERENCIA', 1.0000, 2.00, '2024-01-01', NULL),
            ('SAQUE', 2.0000, 1.00, '2024-01-01', NULL),
            ('DEPOSITO', 0.5000, 0.50, '2024-01-01', NULL)
        """
    )
    ts = datetime.combine(REF_DATE, time(12, 0, 0))
    await conn.execute(
        f"""
        INSERT INTO {SCHEMA}.transacoes
            (conta_origem_id, conta_destino_id, tipo, valor, data_transacao, status)
        VALUES
            ($1, $2, 'TRANSFERENCIA', 1000.00, $3, 'EFETIVADA'),
            ($1, NULL, 'SAQUE', 200.00, $3, 'EFETIVADA'),
            (NULL, $1, 'DEPOSITO', 300.00, $3, 'EFETIVADA'),
            ($1, $2, 'TRANSFERENCIA', 50.00, $3, 'CANCELADA'),
            ($1, NULL, 'TARIFA', 9.99, $3, 'EFETIVADA')
        """,
        origem,
        destino,
        ts,
    )
    # DEPOSITO with origem for ELSE branch (* 0.90)
    await conn.execute(
        f"""
        INSERT INTO {SCHEMA}.transacoes
            (conta_origem_id, conta_destino_id, tipo, valor, data_transacao, status)
        VALUES ($1, NULL, 'DEPOSITO', 400.00, $2, 'EFETIVADA')
        """,
        origem,
        ts,
    )
    return origem, destino


def _expected_totals() -> tuple[Decimal, int]:
    """Hand-computed expected fees for the seed above."""
    # TRANSFERENCIA 1000 → GREATEST(10, 2) = 10
    t_transfer = Decimal("10.00")
    # SAQUE 200 → GREATEST(4, 1) * 1.10 = 4.40
    t_saque = Decimal("4.40")
    # DEPOSITO 300 with origem NULL → skipped
    # CANCELADA / TARIFA → skipped
    # DEPOSITO 400 with origem → GREATEST(2, 0.5) * 0.90 = 1.80
    t_deposito = Decimal("1.80")
    total = t_transfer + t_saque + t_deposito
    return total, 3


@pytest.mark.asyncio
async def test_anexo_e_lote_parity_legacy_vs_modern_set_based():
    """Cursor legacy and set-based modern path produce the same banking state."""
    expected_total, expected_count = _expected_totals()
    conn = await connect()
    try:
        await reset_schema(conn)
        await install_procedure(conn, "anexo_e_sp_processar_lote_taxas.sql")
        await _seed_lote(conn)
        await conn.execute(
            f"CALL {SCHEMA}.sp_processar_lote_taxas($1)",
            REF_DATE,
        )
        snap_legacy = await snapshot_banking(conn)

        await reset_schema(conn)
        await install_procedure(conn, "anexo_e_sp_processar_lote_taxas.sql")
        origem, _destino = await _seed_lote(conn)
        modern_stats = await processar_lote_taxas(conn, REF_DATE)
        snap_modern = await snapshot_banking(conn)

        assert modern_stats["transacoes"] == expected_count
        assert Decimal(str(modern_stats["total_taxas"])) == expected_total

        # Balances
        assert snap_legacy["contas"] == snap_modern["contas"]
        origem_saldo = next(c for c in snap_modern["contas"] if c["id"] == origem)["saldo"]
        assert Decimal(origem_saldo) == Decimal("5000.00") - expected_total

        # Fee transactions
        legacy_tarifas = [t for t in snap_legacy["transacoes"] if t["tipo"] == "TARIFA"]
        modern_tarifas = [t for t in snap_modern["transacoes"] if t["tipo"] == "TARIFA"]
        # seed had 1 TARIFA + 3 new
        assert len(legacy_tarifas) == len(modern_tarifas) == 4
        legacy_fee_sum = sum(
            Decimal(t["valor"]) for t in legacy_tarifas if t["valor"] != "9.99"
        )
        modern_fee_sum = sum(
            Decimal(t["valor"]) for t in modern_tarifas if t["valor"] != "9.99"
        )
        assert legacy_fee_sum == modern_fee_sum == expected_total

        legacy_applied = [
            row for row in snap_legacy["logs"] if row["acao"] == "TARIFA_APLICADA"
        ]
        modern_applied = [
            row for row in snap_modern["logs"] if row["acao"] == "TARIFA_APLICADA"
        ]
        assert len(legacy_applied) == len(modern_applied) == expected_count

        legacy_lote = next(
            row for row in snap_legacy["logs"] if row["acao"] == "LOTE_PROCESSADO"
        )
        modern_lote = next(
            row for row in snap_modern["logs"] if row["acao"] == "LOTE_PROCESSADO"
        )
        compact = legacy_lote["detalhes"].replace(" ", "")
        assert '"transacoes":3' in compact
        assert str(expected_count) in modern_lote["detalhes"]
        assert modern_lote["acao"] == legacy_lote["acao"] == "LOTE_PROCESSADO"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_anexo_e_empty_day_still_logs_lote():
    conn = await connect()
    try:
        await reset_schema(conn)
        await install_procedure(conn, "anexo_e_sp_processar_lote_taxas.sql")
        await seed_client_and_accounts(conn)
        await conn.execute(f"CALL {SCHEMA}.sp_processar_lote_taxas($1)", REF_DATE)
        snap_legacy = await snapshot_banking(conn)

        await reset_schema(conn)
        await install_procedure(conn, "anexo_e_sp_processar_lote_taxas.sql")
        await seed_client_and_accounts(conn)
        stats = await processar_lote_taxas(conn, REF_DATE)
        snap_modern = await snapshot_banking(conn)

        assert stats["transacoes"] == 0
        assert stats["total_taxas"] == Decimal("0")
        assert any(row["acao"] == "LOTE_PROCESSADO" for row in snap_legacy["logs"])
        assert any(row["acao"] == "LOTE_PROCESSADO" for row in snap_modern["logs"])
        assert snap_legacy["contas"] == snap_modern["contas"]
    finally:
        await conn.close()


def test_anexo_e_fixture_exists():
    assert (FIXTURES / "anexo_e_sp_processar_lote_taxas.sql").exists()
