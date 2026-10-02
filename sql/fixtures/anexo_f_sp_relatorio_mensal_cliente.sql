-- =============================================================
-- Anexo F: sp_relatorio_mensal_cliente
-- Complexidade: Muito Alta
-- Gera relatorio mensal de movimentacao de um cliente.
-- Usa CTE recursiva para encadear meses, chama fn_saldo_cliente
-- aninhada e retorna SETOF via RETURN QUERY. Captura excecao
-- com fallback degradado.
-- =============================================================

CREATE OR REPLACE FUNCTION sp_relatorio_mensal_cliente(
    p_cliente_id  BIGINT,
    p_data_inicio DATE,
    p_data_fim    DATE
)
RETURNS TABLE (
    mes_referencia    DATE,
    total_creditos    NUMERIC(18,2),
    total_debitos     NUMERIC(18,2),
    saldo_consolidado NUMERIC(18,2),
    qtd_transacoes    INT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_saldo_atual NUMERIC(18,2);
BEGIN
    IF p_data_inicio > p_data_fim THEN
        RAISE EXCEPTION 'Periodo invalido: inicio % > fim %', p_data_inicio, p_data_fim;
    END IF;

    v_saldo_atual := fn_saldo_cliente(p_cliente_id);
    RAISE NOTICE 'Saldo atual do cliente %: %', p_cliente_id, v_saldo_atual;

    RETURN QUERY
    WITH RECURSIVE meses AS (
        SELECT DATE_TRUNC('month', p_data_inicio)::DATE AS mes
        UNION ALL
        SELECT (mes + INTERVAL '1 month')::DATE
          FROM meses
         WHERE mes < DATE_TRUNC('month', p_data_fim)
    ),
    movimento AS (
        SELECT
            DATE_TRUNC('month', t.data_transacao)::DATE AS mes,
            SUM(CASE WHEN t.conta_destino_id IN (
                    SELECT id FROM contas WHERE cliente_id = p_cliente_id
                ) THEN t.valor ELSE 0 END) AS creditos,
            SUM(CASE WHEN t.conta_origem_id IN (
                    SELECT id FROM contas WHERE cliente_id = p_cliente_id
                ) THEN t.valor ELSE 0 END) AS debitos,
            COUNT(*) AS qtd
          FROM transacoes t
         WHERE t.status = 'EFETIVADA'
           AND t.data_transacao >= p_data_inicio
           AND t.data_transacao <  p_data_fim + INTERVAL '1 day'
           AND (
               t.conta_origem_id  IN (SELECT id FROM contas WHERE cliente_id = p_cliente_id)
            OR t.conta_destino_id IN (SELECT id FROM contas WHERE cliente_id = p_cliente_id)
           )
         GROUP BY 1
    )
    SELECT
        m.mes                                       AS mes_referencia,
        COALESCE(mv.creditos, 0)                    AS total_creditos,
        COALESCE(mv.debitos,  0)                    AS total_debitos,
        v_saldo_atual + COALESCE(mv.creditos, 0)
                      - COALESCE(mv.debitos,  0)    AS saldo_consolidado,
        COALESCE(mv.qtd, 0)::INT                    AS qtd_transacoes
      FROM meses m
      LEFT JOIN movimento mv ON mv.mes = m.mes
      ORDER BY m.mes;

EXCEPTION
    WHEN OTHERS THEN
        RAISE WARNING 'Falha ao gerar relatorio: %. Retornando linha de fallback.', SQLERRM;

        RETURN QUERY
        SELECT
            DATE_TRUNC('month', p_data_inicio)::DATE,
            0::NUMERIC(18,2),
            0::NUMERIC(18,2),
            COALESCE(v_saldo_atual, 0),
            0::INT;
END;
$$;
