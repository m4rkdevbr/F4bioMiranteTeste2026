"""Behavioral equivalence for Anexo F: legacy PL/pgSQL vs modernized asyncpg."""

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
)
from .behavioral.modern_f import relatorio_mensal_cliente

pytestmark = pytest.mark.skipif(not db_url(), reason="DATABASE_URL_SYNC not configured")

INICIO = date(2024, 1, 15)
FIM = date(2024, 3, 10)


async def _install_f(conn) -> None:
    await install_procedure(conn, "anexo_b_fn_saldo_cliente.sql")
    await install_procedure(conn, "anexo_f_sp_relatorio_mensal_cliente.sql")


async def _seed_relatorio(conn) -> int:
    cliente_id = await conn.fetchval(
        f"""
        INSERT INTO {SCHEMA}.clientes (nome, cpf, status)
        VALUES ('Cliente Relatorio', '32345678901', 'ATIVO')
        RETURNING id
        """
    )
    conta_id = await conn.fetchval(
        f"""
        INSERT INTO {SCHEMA}.contas
            (cliente_id, agencia, numero, tipo, saldo, status)
        VALUES ($1, '0001', '30001', 'CORRENTE', 1000.00, 'ATIVA')
        RETURNING id
        """,
        cliente_id,
    )
    other = await conn.fetchval(
        f"""
        INSERT INTO {SCHEMA}.clientes (nome, cpf, status)
        VALUES ('Outro', '32345678902', 'ATIVO')
        RETURNING id
        """
    )
    other_conta = await conn.fetchval(
        f"""
        INSERT INTO {SCHEMA}.contas
            (cliente_id, agencia, numero, tipo, saldo, status)
        VALUES ($1, '0001', '30002', 'CORRENTE', 500.00, 'ATIVA')
        RETURNING id
        """,
        other,
    )

    rows = [
        # Jan credit
        (None, conta_id, "DEPOSITO", "200.00", datetime.combine(date(2024, 1, 20), time(10))),
        # Jan debit
        (conta_id, other_conta, "TRANSFERENCIA", "50.00", datetime.combine(date(2024, 1, 25), time(11))),
        # Feb debit
        (conta_id, None, "SAQUE", "30.00", datetime.combine(date(2024, 2, 5), time(12))),
        # Mar credit
        (other_conta, conta_id, "TRANSFERENCIA", "80.00", datetime.combine(date(2024, 3, 1), time(9))),
        # Outside window / cancelled — ignored for aggregates
        (conta_id, None, "SAQUE", "5.00", datetime.combine(date(2023, 12, 31), time(9))),
        (conta_id, None, "SAQUE", "7.00", datetime.combine(date(2024, 2, 8), time(9))),
    ]
    # Mark last in-window saque as CANCELADA so it must not count
    for i, (origem, destino, tipo, valor, ts) in enumerate(rows):
        status = "CANCELADA" if i == 5 else "EFETIVADA"
        await conn.execute(
            f"""
            INSERT INTO {SCHEMA}.transacoes
                (conta_origem_id, conta_destino_id, tipo, valor, data_transacao, status)
            VALUES ($1, $2, $3, $4::numeric, $5, $6)
            """,
            origem,
            destino,
            tipo,
            valor,
            ts,
            status,
        )
    return int(cliente_id)


def _normalize(rows) -> list[dict]:
    out = []
    for r in rows:
        item = dict(r)
        out.append(
            {
                "mes_referencia": item["mes_referencia"],
                "total_creditos": Decimal(str(item["total_creditos"])),
                "total_debitos": Decimal(str(item["total_debitos"])),
                "saldo_consolidado": Decimal(str(item["saldo_consolidado"])),
                "qtd_transacoes": int(item["qtd_transacoes"]),
            }
        )
    return out


async def _run_legacy(conn, cliente_id: int):
    rows = await conn.fetch(
        f"""
        SELECT mes_referencia, total_creditos, total_debitos,
               saldo_consolidado, qtd_transacoes
          FROM {SCHEMA}.sp_relatorio_mensal_cliente($1, $2, $3)
        """,
        cliente_id,
        INICIO,
        FIM,
    )
    return _normalize(rows)


@pytest.mark.asyncio
async def test_anexo_f_relatorio_parity_legacy_vs_modern():
    """Month spine + credits/debits/qty match between PL/pgSQL and asyncpg."""
    conn = await connect()
    try:
        await reset_schema(conn)
        await _install_f(conn)
        cliente = await _seed_relatorio(conn)
        legacy = await _run_legacy(conn, cliente)

        await reset_schema(conn)
        await _install_f(conn)
        cliente_m = await _seed_relatorio(conn)
        modern = await relatorio_mensal_cliente(conn, cliente_m, INICIO, FIM)

        assert len(legacy) == len(modern) == 3
        assert [r["mes_referencia"] for r in legacy] == [
            date(2024, 1, 1),
            date(2024, 2, 1),
            date(2024, 3, 1),
        ]
        assert modern == legacy

        # Jan: +200 credit, -50 debit, 2 txs; saldo_atual=1000 → 1000+200-50=1150
        assert legacy[0]["total_creditos"] == Decimal("200.00")
        assert legacy[0]["total_debitos"] == Decimal("50.00")
        assert legacy[0]["qtd_transacoes"] == 2
        assert legacy[0]["saldo_consolidado"] == Decimal("1150.00")

        # Feb: -30 debit only (cancelled ignored)
        assert legacy[1]["total_creditos"] == Decimal("0.00")
        assert legacy[1]["total_debitos"] == Decimal("30.00")
        assert legacy[1]["qtd_transacoes"] == 1

        # Mar: +80 credit
        assert legacy[2]["total_creditos"] == Decimal("80.00")
        assert legacy[2]["total_debitos"] == Decimal("0.00")
        assert legacy[2]["qtd_transacoes"] == 1
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_anexo_f_invalid_period_fallback_parity():
    """PL/pgSQL catches invalid period via WHEN OTHERS and returns fallback row."""
    conn = await connect()
    try:
        await reset_schema(conn)
        await _install_f(conn)
        cliente = await _seed_relatorio(conn)

        legacy = _normalize(
            await conn.fetch(
                f"SELECT * FROM {SCHEMA}.sp_relatorio_mensal_cliente($1, $2, $3)",
                cliente,
                FIM,
                INICIO,
            )
        )
        modern = await relatorio_mensal_cliente(conn, cliente, FIM, INICIO)

        assert len(legacy) == len(modern) == 1
        # data_inicio for invalid call is FIM (2024-03-10) → fallback month = March
        assert legacy[0]["mes_referencia"] == modern[0]["mes_referencia"] == date(2024, 3, 1)
        assert legacy[0]["total_creditos"] == modern[0]["total_creditos"] == Decimal("0")
        assert legacy[0]["total_debitos"] == modern[0]["total_debitos"] == Decimal("0")
        assert legacy[0]["qtd_transacoes"] == modern[0]["qtd_transacoes"] == 0
        # v_saldo_atual never assigned before RAISE → COALESCE(...,0) = 0
        assert legacy[0]["saldo_consolidado"] == modern[0]["saldo_consolidado"] == Decimal(
            "0"
        )
    finally:
        await conn.close()


def test_anexo_f_fixture_exists():
    assert (FIXTURES / "anexo_f_sp_relatorio_mensal_cliente.sql").exists()
