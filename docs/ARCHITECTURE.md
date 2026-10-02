# Architecture

## Camadas

```
HTTP (FastAPI) → run_pipeline() → LangGraph
  parsing → semantic_analysis → generation → validation → persist
```

- **API**: validação de payload, health checks, evaluation summary.
- **Grafo**: estado tipado (`PipelineState`), nós isolados, retry condicional.
- **Services**: parser, analyzer, LLM client, prompts, sanitizer.
- **Persistence**: asyncpg → `modernization_history` + `pipeline_evaluation_scores`.
- **Observability**: Langfuse opcional (callbacks + scores).

## Estado

Campos principais: `source_code`, `schema_sql`, `parsed_ir`, `semantic_profile`, `generated_code`, `validation_results`, `evaluation`, `report`, `status`, `history_id`, `run_id`, `retry_count`, `node_timings`.

## Estratégia de tradução

| Padrão PL/pgSQL | Estratégia |
|-----------------|------------|
| Agregação simples | Python + SQL parametrizado |
| OUT params | dataclass / dict |
| FOR UPDATE + multi DML | `session.begin()` + locks SQL |
| Cursor LOOP | set-based / bulk (anti-N+1) |
| WITH RECURSIVE + RETURN QUERY | SQL preservado em `text()` |
| Função aninhada | import do módulo irmão |

## Extensão futura

- Novos dialetos: plugar `SqlDialect` no parser.
- Novos modelos: somente env `LLM_MODEL` / `LLM_FALLBACK_MODELS`.
- Throughput: fila + workers; cache de IR por hash.
