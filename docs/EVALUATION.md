# Evaluation

## Métricas implementadas

| Métrica | Definição |
|---------|-----------|
| `ast_parse_success` | 1 se `ast.parse` ok |
| `pipeline_completion` | 1 se pipeline concluiu sem erro fatal |
| `structural_mapping_score` | Fração de `risk_flags` com evidência no código gerado |
| `generated_loc` | Linhas úteis geradas |
| `ruff_clean` | 1 se ruff sem findings |

Persistidas em `pipeline_evaluation_scores` e opcionalmente como Langfuse scores.

## Endpoint

`GET /evaluation/summary` — médias das últimas N medições.

## Resultados nos anexos B–F (batch local)

Ver tabela no README e arquivos `fixtures/output/*.report.json`.

## O que captura / o que não captura

**Captura:** sintaxe Python, cobertura heurística de riscos, estabilidade do pipeline, LOC gerado.

**Comportamental (Postgres, `DATABASE_URL_SYNC`):**

| Anexo | Arquivo | Contrato |
|-------|---------|----------|
| B | `test_behavioral_anexo_b.py` | Smoke agregação saldo |
| D | `test_behavioral_anexo_d.py` | Transferência atômica + rollbacks |
| E | `test_behavioral_anexo_e.py` | Lote de taxas: cursor ≡ set-based |

Oráculos modernizados em `tests/integration/behavioral/modern_{d,e}.py` (asyncpg), comparados ao `CALL` das fixtures PL/pgSQL no schema isolado `beh`.

**Ainda parcial:** C/F sem golden comportamental end-to-end; similaridade semântica profunda AST SQL↔Python.

## Evolução em produção

1. Golden comportamental para C e F (mesmo padrão D/E).
2. LLM-as-judge com rubrica objetiva (só em amostras).
3. Painel de regressão por anexo (B–F) a cada mudança de prompt/modelo.
