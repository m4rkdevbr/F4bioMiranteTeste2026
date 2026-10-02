"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from modernization_pipeline.services.sql_parser import parse_plpgsql


@pytest.fixture
def sample_fn_saldo() -> str:
    return """
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
""".strip()


@pytest.fixture
def parsed_saldo(sample_fn_saldo: str):
    return parse_plpgsql(sample_fn_saldo)
