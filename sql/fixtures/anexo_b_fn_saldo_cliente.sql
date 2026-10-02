-- =============================================================
-- Anexo B: fn_saldo_cliente
-- Complexidade: Baixa
-- Retorna o saldo total consolidado de todas as contas ativas
-- de um cliente.
-- =============================================================

CREATE OR REPLACE FUNCTION fn_saldo_cliente(p_cliente_id BIGINT)
RETURNS NUMERIC(18,2)
LANGUAGE plpgsql
AS $$
DECLARE
    v_total NUMERIC(18,2);
BEGIN
    SELECT COALESCE(SUM(saldo), 0)
      INTO v_total
      FROM contas
     WHERE cliente_id = p_cliente_id
       AND status = 'ATIVA';

    RETURN v_total;
END;
$$;
