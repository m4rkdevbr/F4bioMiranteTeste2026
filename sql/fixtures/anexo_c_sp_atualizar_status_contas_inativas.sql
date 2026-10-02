-- =============================================================
-- Anexo C: sp_atualizar_status_contas_inativas
-- Complexidade: Baixa-Media
-- Marca como INATIVA toda conta que nao tenha movimentacao
-- ha mais de p_dias dias. Retorna a quantidade de contas afetadas.
-- =============================================================

CREATE OR REPLACE PROCEDURE sp_atualizar_status_contas_inativas(
    IN  p_dias       INT,
    OUT p_afetadas   INT
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_dias IS NULL OR p_dias <= 0 THEN
        RAISE EXCEPTION 'Parametro p_dias deve ser positivo, recebido: %', p_dias;
    END IF;

    UPDATE contas c
       SET status = 'INATIVA'
     WHERE c.status = 'ATIVA'
       AND NOT EXISTS (
            SELECT 1
              FROM transacoes t
             WHERE (t.conta_origem_id = c.id OR t.conta_destino_id = c.id)
               AND t.data_transacao >= NOW() - (p_dias || ' days')::INTERVAL
       );

    GET DIAGNOSTICS p_afetadas = ROW_COUNT;

    INSERT INTO log_auditoria (entidade, acao, detalhes)
    VALUES (
        'contas',
        'INATIVACAO_LOTE',
        jsonb_build_object('dias', p_dias, 'afetadas', p_afetadas)
    );
END;
$$;
