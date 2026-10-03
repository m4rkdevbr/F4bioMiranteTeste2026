"""Modernized Anexo E contract (asyncpg): set-based fee batch (anti N+1)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import asyncpg

from .db import SCHEMA


def _taxa_ajustada(
    valor: Decimal,
    percentual: Decimal,
    minimo: Decimal,
    tipo: str,
) -> Decimal:
    base = max(valor * percentual / Decimal("100"), minimo)
    if tipo == "TRANSFERENCIA":
        return base
    if tipo == "SAQUE":
        return base * Decimal("1.10")
    return base * Decimal("0.90")


async def processar_lote_taxas(
    conn: asyncpg.Connection,
    data_referencia: date,
) -> dict[str, Decimal | int]:
    """Set-based equivalent of ``sp_processar_lote_taxas``."""
    async with conn.transaction():
        txs = await conn.fetch(
            f"""
            SELECT id, conta_origem_id, tipo, valor
              FROM {SCHEMA}.transacoes
             WHERE DATE(data_transacao) = $1
               AND status = 'EFETIVADA'
               AND tipo <> 'TARIFA'
             ORDER BY id
            """,
            data_referencia,
        )
        taxas = await conn.fetch(
            f"""
            SELECT DISTINCT ON (tipo_operacao)
                   tipo_operacao, percentual, valor_minimo
              FROM {SCHEMA}.taxas
             WHERE vigente_de <= $1
               AND (vigente_ate IS NULL OR vigente_ate >= $1)
             ORDER BY tipo_operacao, vigente_de DESC
            """,
            data_referencia,
        )
        taxa_by_tipo = {
            r["tipo_operacao"]: (
                Decimal(str(r["percentual"])),
                Decimal(str(r["valor_minimo"])),
            )
            for r in taxas
        }

        debit_by_conta: dict[int, Decimal] = {}
        novas_tarifas: list[tuple[int, Decimal]] = []
        logs: list[tuple[int, str, Decimal, Decimal, Decimal]] = []
        total = Decimal("0")
        count = 0

        for row in txs:
            origem = row["conta_origem_id"]
            tipo = row["tipo"]
            if origem is None or tipo not in taxa_by_tipo:
                continue
            percentual, minimo = taxa_by_tipo[tipo]
            valor = Decimal(str(row["valor"]))
            taxa = _taxa_ajustada(valor, percentual, minimo, tipo)
            debit_by_conta[int(origem)] = debit_by_conta.get(int(origem), Decimal("0")) + taxa
            novas_tarifas.append((int(origem), taxa))
            logs.append((int(row["id"]), tipo, valor, percentual, taxa))
            total += taxa
            count += 1

        for conta_id, debit in debit_by_conta.items():
            await conn.execute(
                f"UPDATE {SCHEMA}.contas SET saldo = saldo - $1 WHERE id = $2",
                debit,
                conta_id,
            )

        for origem, taxa in novas_tarifas:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.transacoes
                    (conta_origem_id, tipo, valor, status)
                VALUES ($1, 'TARIFA', $2, 'EFETIVADA')
                """,
                origem,
                taxa,
            )

        for tx_id, tipo, valor, percentual, taxa in logs:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.log_auditoria
                    (entidade, entidade_id, acao, detalhes)
                VALUES (
                    'transacoes', $1, 'TARIFA_APLICADA',
                    jsonb_build_object(
                        'transacao_origem', $1::bigint,
                        'tipo_origem', $2::text,
                        'valor_origem', $3::numeric,
                        'percentual', $4::numeric,
                        'taxa_aplicada', $5::numeric
                    )
                )
                """,
                tx_id,
                tipo,
                valor,
                percentual,
                taxa,
            )

        await conn.execute(
            f"""
            INSERT INTO {SCHEMA}.log_auditoria (entidade, acao, detalhes)
            VALUES (
                'lote_taxas',
                'LOTE_PROCESSADO',
                jsonb_build_object(
                    'data_referencia', $1::date,
                    'transacoes', $2::int,
                    'total_taxas', $3::numeric
                )
            )
            """,
            data_referencia,
            count,
            total,
        )
        return {"transacoes": count, "total_taxas": total}
