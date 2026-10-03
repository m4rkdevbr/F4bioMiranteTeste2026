"""Modernized Anexo D contract (asyncpg): atomic transfer with FOR UPDATE."""

from __future__ import annotations

from decimal import Decimal

import asyncpg

from .db import SCHEMA


class TransferError(RuntimeError):
    """Domain error matching PL/pgSQL RAISE EXCEPTION semantics."""


async def transferir_entre_contas(
    conn: asyncpg.Connection,
    conta_origem: int,
    conta_destino: int,
    valor: Decimal,
) -> None:
    """Python equivalent of ``sp_transferir_entre_contas`` (success path + rollback)."""
    if valor is None or valor <= 0:
        raise TransferError(f"Valor invalido para transferencia: {valor}")
    if conta_origem == conta_destino:
        raise TransferError("Conta de origem e destino nao podem ser iguais")

    async with conn.transaction():
        origem = await conn.fetchrow(
            f"""
            SELECT saldo, status
              FROM {SCHEMA}.contas
             WHERE id = $1
             FOR UPDATE
            """,
            conta_origem,
        )
        if origem is None:
            raise TransferError(f"Conta de origem {conta_origem} nao encontrada")

        destino = await conn.fetchrow(
            f"""
            SELECT status
              FROM {SCHEMA}.contas
             WHERE id = $1
             FOR UPDATE
            """,
            conta_destino,
        )
        if destino is None:
            raise TransferError(f"Conta de origem {conta_destino} nao encontrada")

        if origem["status"] != "ATIVA" or destino["status"] != "ATIVA":
            raise TransferError("Ambas as contas precisam estar ATIVAS")

        saldo_origem = Decimal(str(origem["saldo"]))
        if saldo_origem < valor:
            raise TransferError(
                f"Saldo insuficiente: saldo={saldo_origem} valor={valor}"
            )

        await conn.execute(
            f"UPDATE {SCHEMA}.contas SET saldo = saldo - $1 WHERE id = $2",
            valor,
            conta_origem,
        )
        await conn.execute(
            f"UPDATE {SCHEMA}.contas SET saldo = saldo + $1 WHERE id = $2",
            valor,
            conta_destino,
        )
        await conn.execute(
            f"""
            INSERT INTO {SCHEMA}.transacoes
                (conta_origem_id, conta_destino_id, tipo, valor)
            VALUES ($1, $2, 'TRANSFERENCIA', $3)
            """,
            conta_origem,
            conta_destino,
            valor,
        )
        await conn.execute(
            f"""
            INSERT INTO {SCHEMA}.log_auditoria
                (entidade, entidade_id, acao, detalhes)
            VALUES (
                'transacoes',
                NULL,
                'TRANSFERENCIA_OK',
                jsonb_build_object(
                    'origem', $1::bigint,
                    'destino', $2::bigint,
                    'valor', $3::numeric
                )
            )
            """,
            conta_origem,
            conta_destino,
            valor,
        )
