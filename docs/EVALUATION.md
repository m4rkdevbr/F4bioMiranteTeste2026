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

**Parcial:** smoke comportamental do Anexo B (`tests/integration/test_behavioral_anexo_b.py`) quando há Postgres.

**Não captura (ainda):** equivalência comportamental completa de C–F; similaridade semântica profunda de AST SQL↔Python.

## Evolução em produção

1. Golden outputs para todas as procedures dos anexos.
2. LLM-as-judge com rubrica objetiva (só em amostras).
3. Painel de regressão por anexo (B–F) a cada mudança de prompt/modelo.
