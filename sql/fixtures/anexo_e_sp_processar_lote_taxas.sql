-- =============================================================
-- Anexo E: sp_processar_lote_taxas
-- Complexidade: Alta
-- Percorre as transacoes efetivadas em uma data, calcula a tarifa
-- aplicavel conforme o tipo, registra a tarifa como uma nova
-- transacao do tipo TARIFA e mantem log detalhado em JSONB.
-- =============================================================

CREATE OR REPLACE PROCEDURE sp_processar_lote_taxas(
    IN p_data_referencia DATE
)
LANGUAGE plpgsql
AS $$
DECLARE
    cur_transacoes CURSOR FOR
        SELECT id, conta_origem_id, tipo, valor
          FROM transacoes
         WHERE DATE(data_transacao) = p_data_referencia
           AND status = 'EFETIVADA'
           AND tipo  <> 'TARIFA';

    v_id           BIGINT;
    v_origem       BIGINT;
    v_tipo         VARCHAR(20);
    v_valor        NUMERIC(18,2);
    v_taxa         NUMERIC(18,2);
    v_percentual   NUMERIC(7,4);
    v_minimo       NUMERIC(18,2);
    v_total_taxas  NUMERIC(18,2) := 0;
    v_count        INT := 0;
BEGIN
    OPEN cur_transacoes;

    LOOP
        FETCH cur_transacoes INTO v_id, v_origem, v_tipo, v_valor;
        EXIT WHEN NOT FOUND;

        SELECT percentual, valor_minimo
          INTO v_percentual, v_minimo
          FROM taxas
         WHERE tipo_operacao = v_tipo
           AND vigente_de <= p_data_referencia
           AND (vigente_ate IS NULL OR vigente_ate >= p_data_referencia)
         ORDER BY vigente_de DESC
         LIMIT 1;

        IF v_percentual IS NULL THEN
            CONTINUE;
        END IF;

        v_taxa := GREATEST(v_valor * v_percentual / 100.0, v_minimo);

        CASE v_tipo
            WHEN 'TRANSFERENCIA' THEN v_taxa := v_taxa;
            WHEN 'SAQUE'         THEN v_taxa := v_taxa * 1.10;
            ELSE                      v_taxa := v_taxa * 0.90;
        END CASE;

        IF v_origem IS NOT NULL THEN
            UPDATE contas SET saldo = saldo - v_taxa WHERE id = v_origem;

            INSERT INTO transacoes (conta_origem_id, tipo, valor, status)
            VALUES (v_origem, 'TARIFA', v_taxa, 'EFETIVADA');

            INSERT INTO log_auditoria (entidade, entidade_id, acao, detalhes)
            VALUES (
                'transacoes', v_id, 'TARIFA_APLICADA',
                jsonb_build_object(
                    'transacao_origem', v_id,
                    'tipo_origem',      v_tipo,
                    'valor_origem',     v_valor,
                    'percentual',       v_percentual,
                    'taxa_aplicada',    v_taxa
                )
            );

            v_total_taxas := v_total_taxas + v_taxa;
            v_count       := v_count + 1;
        END IF;
    END LOOP;

    CLOSE cur_transacoes;

    INSERT INTO log_auditoria (entidade, acao, detalhes)
    VALUES (
        'lote_taxas', 'LOTE_PROCESSADO',
        jsonb_build_object(
            'data_referencia', p_data_referencia,
            'transacoes',      v_count,
            'total_taxas',     v_total_taxas
        )
    );
END;
$$;
