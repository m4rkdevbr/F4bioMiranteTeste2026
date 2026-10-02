"""
Atualiza o status de contas inativas com base na ausencia de transacoes recentes.
"""

import logging
from typing import Dict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger(__name__)

async def sp_atualizar_status_contas_inativas(
    connection: AsyncConnection,
    p_dias: int
) -> Dict[str, int]:
    """
    Atualiza o status de contas inativas e retorna a quantidade de contas afetadas.

    Args:
        connection: Conexão assíncrona com o banco de dados.
        p_dias: Número de dias para considerar inatividade (deve ser positivo).

    Returns:
        Dicionário com a chave 'p_afetadas' contendo o número de contas atualizadas.

    Raises:
        ValueError: Se p_dias for nulo ou não positivo.
    """
    if p_dias is None or p_dias <= 0:
        raise ValueError(f"Parametro p_dias deve ser positivo, recebido: {p_dias}")

    async with connection.begin():
        # Atualiza contas inativas
        update_stmt = text(
            """
            UPDATE contas c
               SET status = 'INATIVA'
             WHERE c.status = 'ATIVA'
               AND NOT EXISTS (
                    SELECT 1
                      FROM transacoes t
                     WHERE (t.conta_origem_id = c.id OR t.conta_destino_id = c.id)
                       AND t.data_transacao >= NOW() - (:p_dias * interval '1 day')
               )
            """
        )
        result = await connection.execute(update_stmt, {"p_dias": p_dias})
        rowcount = result.rowcount

        # Insere registro de auditoria
        insert_stmt = text(
            """
            INSERT INTO log_auditoria (entidade, acao, detalhes)
            VALUES (
                'contas',
                'INATIVACAO_LOTE',
                :detalhes
            )
            """
        )
        detalhes = {"dias": p_dias, "afetadas": rowcount}
        await connection.execute(insert_stmt, {"detalhes": detalhes})

    return {"p_afetadas": rowcount}
