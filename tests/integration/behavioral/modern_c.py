"""Modernized Anexo C contract (asyncpg): bulk inactivate stale active accounts."""

from __future__ import annotations

import asyncpg

from .db import SCHEMA


class InativacaoError(RuntimeError):
    """Domain error matching PL/pgSQL RAISE EXCEPTION semantics."""


async def atualizar_status_contas_inativas(conn: asyncpg.Connection, dias: int) -> int:
    """Python equivalent of ``sp_atualizar_status_contas_inativas``."""
    if dias is None or dias <= 0:
        raise InativacaoError(f"Parametro p_dias deve ser positivo, recebido: {dias}")

    async with conn.transaction():
        result = await conn.execute(
            f"""
            UPDATE {SCHEMA}.contas c
               SET status = 'INATIVA'
             WHERE c.status = 'ATIVA'
               AND NOT EXISTS (
                    SELECT 1
                      FROM {SCHEMA}.transacoes t
                     WHERE (t.conta_origem_id = c.id OR t.conta_destino_id = c.id)
                       AND t.data_transacao >= NOW() - make_interval(days => $1)
               )
            """,
            dias,
        )
        # asyncpg returns status like "UPDATE 2"
        afetadas = int(result.split()[-1]) if result else 0
        await conn.execute(
            f"""
            INSERT INTO {SCHEMA}.log_auditoria (entidade, acao, detalhes)
            VALUES (
                'contas',
                'INATIVACAO_LOTE',
                jsonb_build_object('dias', $1::int, 'afetadas', $2::int)
            )
            """,
            dias,
            afetadas,
        )
        return afetadas
