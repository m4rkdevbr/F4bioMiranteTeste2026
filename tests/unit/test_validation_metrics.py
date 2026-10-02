"""Unit tests for sanitizer, AST validation and metrics."""

from __future__ import annotations

from modernization_pipeline.services.code_sanitizer import sanitize_generated_code
from modernization_pipeline.validation.ast_check import check_ast
from modernization_pipeline.validation.metrics import compute_metrics, derive_status


def test_sanitize_strips_fences():
    raw = "```python\nprint('ok')\n```"
    assert sanitize_generated_code(raw).strip() == "print('ok')"


def test_ast_ok_and_fail():
    assert check_ast("x = 1\n")["ok"] is True
    assert check_ast("def broken(:\n")["ok"] is False


def test_metrics_and_status():
    code = """
import logging
from dataclasses import dataclass

async def run():
    try:
        async with session.begin():
            await session.execute(text('SELECT 1 FOR UPDATE'))
    except Exception:
        raise
"""
    profile = {
        "risk_flags": [
            {"code": "for_update"},
            {"code": "exception_handler"},
            {"code": "raise_notice"},
        ]
    }
    validation = {"ast": check_ast(code), "ruff": {"ok": True, "issues": []}}
    metrics = compute_metrics(
        generated_code=code,
        semantic_profile=profile,
        pipeline_ok=True,
        validation_results=validation,
    )
    assert metrics["scores"]["ast_parse_success"] == 1.0
    assert metrics["scores"]["structural_mapping_score"] > 0
    assert derive_status(generated_code=code, validation_results=validation, had_fatal_error=False) in {
        "success",
        "partial",
    }
