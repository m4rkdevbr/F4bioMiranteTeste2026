"""Modernized Anexo F contract (asyncpg): monthly client report with month spine."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import asyncpg

from .db import SCHEMA


class RelatorioError(RuntimeError):
    """Domain error matching PL/pgSQL RAISE EXCEPTION semantics."""


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _add_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _month_spine(inicio: date, fim: date) -> list[date]:
    months: list[date] = []
    cur = _month_start(inicio)
    last = _month_start(fim)
    while cur <= last:
        months.append(cur)
        cur = _add_month(cur)
    return months


async def _saldo_cliente(conn: asyncpg.Connection, cliente_id: int) -> Decimal:
    value = await conn.fetchval(
        f"""
        SELECT COALESCE(SUM(saldo), 0)
          FROM {SCHEMA}.contas
         WHERE cliente_id = $1
           AND status = 'ATIVA'
        """,
        cliente_id,
    )
    return Decimal(str(value))


async def relatorio_mensal_cliente(
    conn: asyncpg.Connection,
    cliente_id: int,
    data_inicio: date,
    data_fim: date,
) -> list[dict[str, Any]]:
    """Python equivalent of ``sp_relatorio_mensal_cliente`` (happy path + fallback).

    Invalid period raises internally and is swallowed like PL/pgSQL ``EXCEPTION WHEN
    OTHERS`` — returning a single degraded row.
    """
    saldo_atual = Decimal("0")
    try:
        if data_inicio > data_fim:
            raise RelatorioError(
                f"Periodo invalido: inicio {data_inicio} > fim {data_fim}"
            )

        saldo_atual = await _saldo_cliente(conn, cliente_id)
        conta_ids = [
            int(r["id"])
            for r in await conn.fetch(
                f"SELECT id FROM {SCHEMA}.contas WHERE cliente_id = $1",
                cliente_id,
            )
        ]
        if not conta_ids:
            conta_ids = [-1]  # no match in IN clauses

        fim_exclusive = data_fim + timedelta(days=1)
        movimento = await conn.fetch(
            f"""
            SELECT
                DATE_TRUNC('month', t.data_transacao)::DATE AS mes,
                SUM(
                    CASE WHEN t.conta_destino_id = ANY($1::bigint[])
                         THEN t.valor ELSE 0 END
                ) AS creditos,
                SUM(
                    CASE WHEN t.conta_origem_id = ANY($1::bigint[])
                         THEN t.valor ELSE 0 END
                ) AS debitos,
                COUNT(*)::INT AS qtd
              FROM {SCHEMA}.transacoes t
             WHERE t.status = 'EFETIVADA'
               AND t.data_transacao >= $2
               AND t.data_transacao < $3
               AND (
                   t.conta_origem_id = ANY($1::bigint[])
                OR t.conta_destino_id = ANY($1::bigint[])
               )
             GROUP BY 1
            """,
            conta_ids,
            data_inicio,
            fim_exclusive,
        )
        by_mes = {
            r["mes"]: (
                Decimal(str(r["creditos"])),
                Decimal(str(r["debitos"])),
                int(r["qtd"]),
            )
            for r in movimento
        }

        rows: list[dict[str, Any]] = []
        for mes in _month_spine(data_inicio, data_fim):
            creditos, debitos, qtd = by_mes.get(mes, (Decimal("0"), Decimal("0"), 0))
            rows.append(
                {
                    "mes_referencia": mes,
                    "total_creditos": creditos,
                    "total_debitos": debitos,
                    "saldo_consolidado": saldo_atual + creditos - debitos,
                    "qtd_transacoes": qtd,
                }
            )
        return rows
    except Exception:
        return [
            {
                "mes_referencia": _month_start(data_inicio),
                "total_creditos": Decimal("0"),
                "total_debitos": Decimal("0"),
                "saldo_consolidado": saldo_atual,
                "qtd_transacoes": 0,
            }
        ]
