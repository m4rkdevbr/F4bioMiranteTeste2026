#!/usr/bin/env python3
"""Batch-run annexes B–F through the modernization pipeline."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from modernization_pipeline.graph import run_pipeline  # noqa: E402

FIXTURES = ROOT / "sql" / "fixtures"
OUTPUT = ROOT / "fixtures" / "output"

ANNEXES = [
    ("anexo_b_fn_saldo_cliente", "anexo_b_fn_saldo_cliente.sql"),
    ("anexo_c_sp_atualizar_status_contas_inativas", "anexo_c_sp_atualizar_status_contas_inativas.sql"),
    ("anexo_d_sp_transferir_entre_contas", "anexo_d_sp_transferir_entre_contas.sql"),
    ("anexo_e_sp_processar_lote_taxas", "anexo_e_sp_processar_lote_taxas.sql"),
    ("anexo_f_sp_relatorio_mensal_cliente", "anexo_f_sp_relatorio_mensal_cliente.sql"),
]


async def run_one(name: str, sql_file: Path, schema_sql: str | None) -> dict:
    source = sql_file.read_text(encoding="utf-8")
    result = await run_pipeline(
        source_code=source,
        schema_sql=schema_sql,
        procedure_name=name,
        metadata={"annex": name},
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    code = result.get("generated_code") or ""
    (OUTPUT / f"{name}.py").write_text(code, encoding="utf-8")
    report = result.get("report") or {}
    report_path = OUTPUT / f"{name}.report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "name": name,
        "status": result.get("status"),
        "history_id": result.get("history_id"),
        "ast_ok": ((result.get("validation_results") or {}).get("ast") or {}).get("ok"),
        "model": ((result.get("generation_meta") or {}).get("model_used")),
    }


async def amain(selected: list[str] | None = None) -> int:
    schema_path = FIXTURES / "anexo_a_schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8") if schema_path.exists() else None
    summaries = []
    for name, filename in ANNEXES:
        if selected and name not in selected and filename not in selected:
            continue
        print(f"==> Running {name}")
        summary = await run_one(name, FIXTURES / filename, schema_sql)
        print(json.dumps(summary, ensure_ascii=False))
        summaries.append(summary)
    (OUTPUT / "batch_summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    failures = [s for s in summaries if s.get("status") == "failure"]
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run annex fixtures B–F")
    parser.add_argument("--only", nargs="*", help="Optional annex names to run")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(amain(args.only)))


if __name__ == "__main__":
    main()
