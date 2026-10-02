"""Módulo para consultar o saldo consolidado de contas ativas de um cliente."""

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ["fn_saldo_cliente"]


async def fn_saldo_cliente(p_cliente_id: int, session: AsyncSession) -> Decimal:
    """Retorna o saldo total consolidado das contas ativas do cliente."""
    sql = text(
        """
        SELECT COALESCE(SUM(saldo), 0)
        FROM contas
        WHERE cliente_id = :cliente_id
          AND status = :status
        """
    )

    result = await session.execute(
        sql,
        {"cliente_id": p_cliente_id, "status": "ATIVA"},
    )
    total = result.scalar()

    return Decimal(total) if total is not None else Decimal("0")
