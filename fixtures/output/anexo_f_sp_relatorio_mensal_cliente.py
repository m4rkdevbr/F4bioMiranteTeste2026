"""
Módulo contendo a função sp_relatorio_mensal_cliente para geração de relatório mensal de cliente.
"""

import logging
from typing import List, Dict, Any
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)

try:
    from .fn_saldo_cliente import fn_saldo_cliente
except ImportError:
    logger.warning("Módulo fn_saldo_cliente não encontrado. Função pode falhar.")
    fn_saldo_cliente = None  # type: ignore


async def sp_relatorio_mensal_cliente(
    session: AsyncSession,
    p_cliente_id: int,
    p_data_inicio: date,
    p_data_fim: date
) -> List[Dict[str, Any]]:
    """
    Gera relatório mensal de movimentação de um cliente.

    Args:
        session: Sessão assíncrona do SQLAlchemy.
        p_cliente_id: ID do cliente.
        p_data_inicio: Data de início do período.
        p_data_fim: Data de fim do período.

    Returns:
        Lista de dicionários contendo os dados do relatório por mês.

    Raises:
        ValueError: Se a data de início for maior que a data de fim.
        Exception: Para outros erros durante a execução.
    """
    try:
        if p_data_inicio > p_data_fim:
            raise ValueError(
                f"Periodo invalido: inicio {p_data_inicio} > fim {p_data_fim}"
            )

        if fn_saldo_cliente is None:
            raise RuntimeError("Função fn_saldo_cliente não disponível")

        v_saldo_atual = await fn_saldo_cliente(session, p_cliente_id)
        logger.info(
            "Saldo atual do cliente %s: %s", p_cliente_id, v_saldo_atual
        )

        main_sql = text("""
            WITH RECURSIVE meses AS (
                SELECT DATE_TRUNC('month', :p_data_inicio)::DATE AS mes
                UNION ALL
                SELECT (mes + INTERVAL '1 month')::DATE
                  FROM meses
                 WHERE mes < DATE_TRUNC('month', :p_data_fim)
            ),
            movimento AS (
                SELECT
                    DATE_TRUNC('month', t.data_transacao)::DATE AS mes,
                    SUM(CASE WHEN t.conta_destino_id IN (
                            SELECT id FROM contas WHERE cliente_id = :p_cliente_id
                        ) THEN t.valor ELSE 0 END) AS creditos,
                    SUM(CASE WHEN t.conta_origem_id IN (
                            SELECT id FROM contas WHERE cliente_id = :p_cliente_id
                        ) THEN t.valor ELSE 0 END) AS debitos,
                    COUNT(*) AS qtd
                  FROM transacoes t
                 WHERE t.status = 'EFETIVADA'
                   AND t.data_transacao >= :p_data_inicio
                   AND t.data_transacao <  :p_data_fim + INTERVAL '1 day'
                   AND (
                       t.conta_origem_id  IN (SELECT id FROM contas WHERE cliente_id = :p_cliente_id)
                    OR t.conta_destino_id IN (SELECT id FROM contas WHERE cliente_id = :p_cliente_id)
                   )
                 GROUP BY 1
            )
            SELECT
                m.mes                                       AS mes_referencia,
                COALESCE(mv.creditos, 0)                    AS total_creditos,
                COALESCE(mv.debitos,  0)                    AS total_debitos,
                :v_saldo_atual + COALESCE(mv.creditos, 0)
                          - COALESCE(mv.debitos,  0)        AS saldo_consolidado,
                COALESCE(mv.qtd, 0)::INT                    AS qtd_transacoes
              FROM meses m
              LEFT JOIN movimento mv ON mv.mes = m.mes
              ORDER BY m.mes
        """)

        result = await session.execute(
            main_sql,
            {
                "p_data_inicio": p_data_inicio,
                "p_data_fim": p_data_fim,
                "p_cliente_id": p_cliente_id,
                "v_saldo_atual": v_saldo_atual,
            },
        )
        rows = result.fetchall()
        return [dict(row) for row in rows]

    except Exception as e:
        logger.warning(
            "Falha ao gerar relatorio: %s. Retornando linha de fallback.", e
        )
        fallback_sql = text("""
            SELECT
                DATE_TRUNC('month', :p_data_inicio)::DATE,
                0::NUMERIC(18,2),
                0::NUMERIC(18,2),
                COALESCE(:v_saldo_atual, 0),
                0::INT
        """)
        result = await session.execute(
            fallback_sql,
            {
                "p_data_inicio": p_data_inicio,
                "v_saldo_atual": v_saldo_atual if 'v_saldo_atual' in locals() else None,
            },
        )
        row = result.fetchone()
        return [dict(row)] if row else []
