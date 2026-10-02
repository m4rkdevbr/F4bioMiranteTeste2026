# -*- coding: utf-8 -*-
"""
Módulo para processamento em lote de taxas bancárias.
Equivalente ao procedimento PL/pgSQL sp_processar_lote_taxas.
"""

import logging
from collections import defaultdict
from decimal import Decimal
from typing import List, Dict, Any
from datetime import date

from sqlalchemy import select, update, insert, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import JSONB

# Definição das tabelas com base no esquema fornecido
from sqlalchemy import MetaData, Table, Column, BigInteger, String, Numeric, DateTime

metadata = MetaData()

# Tabela contas
contas = Table(
    'contas', metadata,
    Column('id', BigInteger, primary_key=True),
    Column('cliente_id', BigInteger),
    Column('agencia', String(10)),
    Column('numero', String(20)),
    Column('tipo', String(20)),
    Column('saldo', Numeric(18, 2)),
    Column('status', String(20)),
    Column('data_abertura', DateTime)
)

# Tabela transacoes
transacoes = Table(
    'transacoes', metadata,
    Column('id', BigInteger, primary_key=True),
    Column('conta_origem_id', BigInteger),
    Column('conta_destino_id', BigInteger),
    Column('tipo', String(20)),
    Column('valor', Numeric(18, 2)),
    Column('data_transacao', DateTime),
    Column('status', String(20))
)

# Tabela taxas
taxas = Table(
    'taxas', metadata,
    Column('id', BigInteger, primary_key=True),
    Column('tipo_operacao', String(20)),
    Column('percentual', Numeric(7, 4)),
    Column('valor_minimo', Numeric(18, 2)),
    Column('vigente_de', Date),
    Column('vigente_ate', Date)
)

# Tabela log_auditoria
log_auditoria = Table(
    'log_auditoria', metadata,
    Column('id', BigInteger, primary_key=True),
    Column('entidade', String(50)),
    Column('entidade_id', BigInteger),
    Column('acao', String(50)),
    Column('detalhes', JSONB),
    Column('criado_em', DateTime)
)

logger = logging.getLogger(__name__)

async def sp_processar_lote_taxas(session: AsyncSession, p_data_referencia: date) -> None:
    """
    Processa taxas para transações efetivadas em uma data específica.
    
    Args:
        session: Sessão assíncrona do SQLAlchemy.
        p_data_referencia: Data de referência para filtrar transações.
    """
    # Busca transações efetivadas na data de referência, excluindo tarifas
    stmt_transacoes = select(
        transacoes.c.id,
        transacoes.c.conta_origem_id,
        transacoes.c.tipo,
        transacoes.c.valor
    ).where(
        and_(
            func.date(transacoes.c.data_transacao) == p_data_referencia,
            transacoes.c.status == 'EFETIVADA',
            transacoes.c.tipo != 'TARIFA'
        )
    )
    
    result = await session.execute(stmt_transacoes)
    transacoes_lista = result.fetchall()
    
    if not transacoes_lista:
        # Ainda registra o lote processado com zero transações
        await _registrar_log_lote(session, p_data_referencia, 0, Decimal('0'))
        return
    
    # Extrai tipos de transação distintos para buscar taxas
    tipos_distintos = {row.tipo for row in transacoes_lista}
    
    # Busca as taxas mais recentes válidas para cada tipo na data de referência
    taxas_dict: Dict[str, tuple[Decimal, Decimal]] = {}
    if tipos_distintos:
        stmt_taxas = select(
            taxas.c.tipo_operacao,
            taxas.c.percentual,
            taxas.c.valor_minimo
        ).where(
            and_(
                taxas.c.tipo_operacao.in_(tipos_distintos),
                taxas.c.vigente_de <= p_data_referencia,
                or_(
                    taxas.c.vigente_ate.is_(None),
                    taxas.c.vigente_ate >= p_data_referencia
                )
            )
        ).order_by(
            taxas.c.tipo_operacao,
            taxas.c.vigente_de.desc()
        ).distinct(taxas.c.tipo_operacao)
        
        result_taxas = await session.execute(stmt_taxas)
        for row in result_taxas.fetchall():
            taxas_dict[row.tipo_operacao] = (row.percentual, row.valor_minimo)
    
    # Preparação para atualizações em lote
    atualizacoes_contas: Dict[BigInteger, Decimal] = defaultdict(Decimal)
    novas_transacoes: List[Dict[str, Any]] = []
    logs_auditoria_tarifa: List[Dict[str, Any]] = []
    total_taxas = Decimal('0')
    count_processadas = 0
    
    for row in transacoes_lista:
        v_id = row.id
        v_origem = row.conta_origem_id
        v_tipo = row.tipo
        v_valor = row.valor
        
        # Pula se não houver taxa definida para o tipo
        if v_tipo not in taxas_dict:
            continue
            
        v_percentual, v_minimo = taxas_dict[v_tipo]
        
        # Calcula a taxa base
        v_taxa_base = (v_valor * v_percentual) / Decimal('100')
        v_taxa = max(v_taxa_base, v_minimo)
        
        # Ajusta conforme o tipo de transação
        if v_tipo == 'TRANSFERENCIA':
            v_taxa_ajustada = v_taxa
        elif v_tipo == 'SAQUE':
            v_taxa_ajustada = v_taxa * Decimal('1.10')
        else:
            v_taxa_ajustada = v_taxa * Decimal('0.90')
        
        # Processa apenas se houver conta de origem válida
        if v_origem is not None:
            # Acumula para atualização de saldo em lote
            atualizacoes_contas[v_origem] += v_taxa_ajustada
            
            # Prepara nova transação de tarifa
            novas_transacoes.append({
                'conta_origem_id': v_origem,
                'tipo': 'TARIFA',
                'valor': v_taxa_ajustada,
                'status': 'EFETIVADA'
            })
            
            # Prepara log de auditoria para a tarifa aplicada
            detalhes_log = {
                'transacao_origem': v_id,
                'tipo_origem': v_tipo,
                'valor_origem': v_valor,
                'percentual': v_percentual,
                'taxa_aplicada': v_taxa_ajustada
            }
            logs_auditoria_tarifa.append({
                'entidade': 'transacoes',
                'entidade_id': v_id,
                'acao': 'TARIFA_APLICADA',
                'detalhes': detalhes_log
            })
            
            total_taxas += v_taxa_ajustada
            count_processadas += 1
    
    # Executa atualizações de saldo em lote por conta
    for conta_id, total_taxa_conta in atualizacoes_contas.items():
        stmt_update = update(contas).where(
            contas.c.id == conta_id
        ).values(
            saldo=contas.c.saldo - total_taxa_conta
        )
        await session.execute(stmt_update)
    
    # Insere novas transações de tarifa em lote
    if novas_transacoes:
        stmt_insert_transacao = insert(transacoes).values(novas_transacoes)
        await session.execute(stmt_insert_transacao)
    
    # Insere logs de auditoria de tarifas aplicadas em lote
    if logs_auditoria_tarifa:
        stmt_insert_log = insert(log_auditoria).values(logs_auditoria_tarifa)
        await session.execute(stmt_insert_log)
    
    # Registra log do lote processado
    await _registrar_log_lote(session, p_data_referencia, count_processadas, total_taxas)

async def _registrar_log_lote(
    session: AsyncSession,
    data_referencia: date,
    quantidade_transacoes: int,
    total_taxas: Decimal
) -> None:
    """Registra o log de processamento do lote."""
    detalhes_lote = {
        'data_referencia': data_referencia,
        'transacoes': quantidade_transacoes,
        'total_taxas': total_taxas
    }
    stmt_log = insert(log_auditoria).values({
        'entidade': 'lote_taxas',
        'acao': 'LOTE_PROCESSADO',
        'detalhes': detalhes_lote
    })
    await session.execute(stmt_log)
