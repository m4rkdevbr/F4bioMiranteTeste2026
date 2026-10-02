"""
Módulo: transferencia_contas
Descrição: Função assíncrona que transfere um valor entre duas contas,
           garantindo validações de saldo, status e registro de transação
           em uma única transação explícita.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Final

from sqlalchemy import text, update, select, insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

# Importa as tabelas definidas no modelo SQLAlchemy do projeto.
# Espera‑se que este módulo exporte objetos Table nomeados:
#   contas, transacoes, log_auditoria
from .models import contas, transacoes, log_auditoria  # type: ignore

logger = logging.getLogger(__name__)

# Mensagens de erro padronizadas (mantém a mesma semântica do PL/pgSQL)
_ERR_INVALID_VALUE: Final = "Valor invalido para transferencia: {valor}"
_ERR_SAME_ACCOUNT: Final = "Conta de origem e destino nao podem ser iguais"
_ERR_ACCOUNT_NOT_FOUND: Final = "Conta de origem {conta} nao encontrada"
_ERR_ACCOUNT_INACTIVE: Final = "Ambas as contas precisam estar ATIVAS"
_ERR_INSUFFICIENT_FUNDS: Final = "Saldo insuficiente: saldo={saldo} valor={valor}"


class TransferError(RuntimeError):
    """Exceção de domínio para falhas na transferência entre contas."""
    pass


async def transferir_entre_contas(
    session: AsyncSession,
    p_conta_origem: int,
    p_conta_destino: int,
    p_valor: Decimal,
) -> None:
    """
    Transfere ``p_valor`` da conta ``p_conta_origem`` para ``p_conta_destino``.

    Args:
        session: Sessão assíncrona do SQLAlchemy.
        p_conta_origem: Identificador da conta de origem.
        p_conta_destino: Identificador da conta de destino.
        p_valor: Valor a ser transferido (deve ser > 0).

    Raises:
        TransferError: Quando alguma regra de negócio é violada.
        SQLAlchemyError: Para falhas de acesso ao banco (propagadas após
                         registrar o log de erro).
    """
    # ---------- Validações iniciais ----------
    if p_valor is None or p_valor <= 0:
        raise TransferError(_ERR_INVALID_VALUE.format(valor=p_valor))

    if p_conta_origem == p_conta_destino:
        raise TransferError(_ERR_SAME_ACCOUNT)

    # ---------- Transação explícita ----------
    try:
        async with session.begin():
            # Bloqueia as linhas das contas envolvidas
            stmt_origem = (
                select(contas.c.saldo, contas.c.status)
                .where(contas.c.id == p_conta_origem)
                .with_for_update()
            )
            result_origem = await session.execute(stmt_origem)
            row_origem = result_origem.fetchone()
            if row_origem is None:
                raise TransferError(_ERR_ACCOUNT_NOT_FOUND.format(conta=p_conta_origem))

            v_saldo_origem: Decimal = row_origem.saldo  # type: ignore[assignment]
            v_status_origem: str = row_origem.status  # type: ignore[assignment]

            stmt_destino = (
                select(contas.c.status)
                .where(contas.c.id == p_conta_destino)
                .with_for_update()
            )
            result_destino = await session.execute(stmt_destino)
            row_destino = result_destino.fetchone()
            if row_destino is None:
                raise TransferError(_ERR_ACCOUNT_NOT_FOUND.format(conta=p_conta_destino))

            v_status_destino: str = row_destino.status  # type: ignore[assignment]

            # Verificações de conta
            if v_saldo_origem is None:
                raise TransferError(_ERR_ACCOUNT_NOT_FOUND.format(conta=p_conta_origem))

            if v_status_origem != "ATIVA" or v_status_destino != "ATIVA":
                raise TransferError(_ERR_ACCOUNT_INACTIVE)

            if v_saldo_origem < p_valor:
                raise TransferError(
                    _ERR_INSUFFICIENT_FUNDS.format(saldo=v_saldo_origem, valor=p_valor)
                )

            # Atualiza saldos
            await session.execute(
                update(contas)
                .where(contas.c.id == p_conta_origem)
                .values(saldo=contas.c.saldo - p_valor)
            )
            await session.execute(
                update(contas)
                .where(contas.c.id == p_conta_destino)
                .values(saldo=contas.c.saldo + p_valor)
            )

            # Registra a transação
            await session.execute(
                insert(transacoes).values(
                    conta_origem_id=p_conta_origem,
                    conta_destino_id=p_conta_destino,
                    tipo="TRANSFERENCIA",
                    valor=p_valor,
                )
            )

            # Log de auditoria de sucesso
            await session.execute(
                insert(log_auditoria).values(
                    entidade="transacoes",
                    entidade_id=None,
                    acao="TRANSFERENCIA_OK",
                    detalhes={
                        "origem": p_conta_origem,
                        "destino": p_conta_destino,
                        "valor": p_valor,
                    },
                )
            )

    except TransferError:
        # Erros de domínio: apenas registra o log de erro e propaga
        await _log_error_audit(session, p_conta_origem, p_conta_destino, p_valor)
        raise
    except SQLAlchemyError as exc:
        # Falhas de acesso ao banco: registra log de erro e propaga
        await _log_error_audit(session, p_conta_origem, p_conta_destino, p_valor, erro=str(exc))
        raise


async def _log_error_audit(
    session: AsyncSession,
    conta_origem: int,
    conta_destino: int,
    valor: Decimal,
    *,
    erro: str | None = None,
) -> None:
    """
    Insere um registro em ``log_auditoria`` descrevendo uma falha de transferência.
    Esta função é chamada dentro do mesmo escopo de exceção; se a transação
    for revertida, o log também será revertido – espelhando o comportamento
    do bloco EXCEPTION do PL/pgSQL original.
    """
    detalhes: dict = {
        "origem": conta_origem,
        "destino": conta_destino,
        "valor": valor,
    }
    if erro is not None:
        detalhes["erro"] = erro

    await session.execute(
        insert(log_auditoria).values(
            entidade="transacoes",
            acao="TRANSFERENCIA_ERRO",
            detalhes=detalhes,
        )
    )
