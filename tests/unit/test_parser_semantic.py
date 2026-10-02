"""Unit tests for SQL/PL/pgSQL parsing and semantic analysis."""

from __future__ import annotations

from pathlib import Path

from modernization_pipeline.services.semantic_analyzer import analyze_semantics
from modernization_pipeline.services.sql_parser import parse_plpgsql

FIXTURES = Path(__file__).resolve().parents[2] / "sql" / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_anexo_b_scalar_function():
    ir = parse_plpgsql(_load("anexo_b_fn_saldo_cliente.sql"))
    assert ir["kind"] == "function"
    assert ir["name"] == "fn_saldo_cliente"
    assert ir["parameters"][0]["name"] == "p_cliente_id"
    assert not ir["errors"]


def test_parse_anexo_c_out_param_and_diagnostics():
    ir = parse_plpgsql(_load("anexo_c_sp_atualizar_status_contas_inativas.sql"))
    assert ir["kind"] == "procedure"
    dirs = {p["name"]: p["direction"] for p in ir["parameters"]}
    assert dirs["p_dias"] == "IN"
    assert dirs["p_afetadas"] == "OUT"
    assert ir["body_constructs"]["has_get_diagnostics"] is True
    profile = analyze_semantics(ir)
    codes = {r["code"] for r in profile["risk_flags"]}
    assert "out_parameters" in codes
    assert "get_diagnostics" in codes


def test_parse_anexo_d_for_update_and_exception():
    ir = parse_plpgsql(_load("anexo_d_sp_transferir_entre_contas.sql"))
    assert ir["body_constructs"]["has_for_update"] is True
    assert ir["body_constructs"]["has_exception"] is True
    profile = analyze_semantics(ir)
    codes = {r["code"] for r in profile["risk_flags"]}
    assert "for_update" in codes
    assert "exception_handler" in codes


def test_parse_anexo_e_cursor_loop():
    ir = parse_plpgsql(_load("anexo_e_sp_processar_lote_taxas.sql"))
    assert ir["cursors"], "expected explicit cursor declaration"
    assert ir["body_constructs"]["has_loop"] is True
    profile = analyze_semantics(ir)
    codes = {r["code"] for r in profile["risk_flags"]}
    assert "cursor_loop" in codes
    assert profile["complexity"] == "high"


def test_parse_anexo_f_recursive_and_nested():
    ir = parse_plpgsql(_load("anexo_f_sp_relatorio_mensal_cliente.sql"))
    assert ir["body_constructs"]["has_recursive_cte"] is True
    assert ir["body_constructs"]["has_return_query"] is True
    assert "fn_saldo_cliente" in ir["nested_calls"]
    profile = analyze_semantics(ir)
    codes = {r["code"] for r in profile["risk_flags"]}
    assert "recursive_cte" in codes
    assert "nested_function_call" in codes
