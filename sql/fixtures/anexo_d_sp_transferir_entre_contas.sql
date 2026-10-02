-- =============================================================
-- Anexo D: sp_transferir_entre_contas
-- Complexidade: Media
-- Transfere um valor entre duas contas em transacao atomica.
-- Valida saldo, status das contas e registra a transacao.
-- =============================================================

CREATE OR REPLACE PROCEDURE sp_transferir_entre_contas(
    IN p_conta_origem   BIGINT,
    IN p_conta_destino  BIGINT,
    IN p_valor          NUMERIC(18,2)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_saldo_origem    NUMERIC(18,2);
    v_status_origem   VARCHAR(20);
    v_status_destino  VARCHAR(20);
BEGIN
    IF p_valor IS NULL OR p_valor <= 0 THEN
        RAISE EXCEPTION 'Valor invalido para transferencia: %', p_valor;
    END IF;

    IF p_conta_origem = p_conta_destino THEN
        RAISE EXCEPTION 'Conta de origem e destino nao podem ser iguais';
    END IF;

    SELECT saldo, status INTO v_saldo_origem, v_status_origem
      FROM contas WHERE id = p_conta_origem FOR UPDATE;

    SELECT status INTO v_status_destino
      FROM contas WHERE id = p_conta_destino FOR UPDATE;

    IF v_saldo_origem IS NULL THEN
        RAISE EXCEPTION 'Conta de origem % nao encontrada', p_conta_origem;
    END IF;

    IF v_status_origem <> 'ATIVA' OR v_status_destino <> 'ATIVA' THEN
        RAISE EXCEPTION 'Ambas as contas precisam estar ATIVAS';
    END IF;

    IF v_saldo_origem < p_valor THEN
        RAISE EXCEPTION 'Saldo insuficiente: saldo=% valor=%', v_saldo_origem, p_valor;
    END IF;

    UPDATE contas SET saldo = saldo - p_valor WHERE id = p_conta_origem;
    UPDATE contas SET saldo = saldo + p_valor WHERE id = p_conta_destino;

    INSERT INTO transacoes (conta_origem_id, conta_destino_id, tipo, valor)
    VALUES (p_conta_origem, p_conta_destino, 'TRANSFERENCIA', p_valor);

    INSERT INTO log_auditoria (entidade, entidade_id, acao, detalhes)
    VALUES (
        'transacoes',
        NULL,
        'TRANSFERENCIA_OK',
        jsonb_build_object(
            'origem',  p_conta_origem,
            'destino', p_conta_destino,
            'valor',   p_valor
        )
    );

EXCEPTION
    WHEN OTHERS THEN
        INSERT INTO log_auditoria (entidade, acao, detalhes)
        VALUES (
            'transacoes',
            'TRANSFERENCIA_ERRO',
            jsonb_build_object(
                'origem',  p_conta_origem,
                'destino', p_conta_destino,
                'valor',   p_valor,
                'erro',    SQLERRM
            )
        );
        RAISE;
END;
$$;
