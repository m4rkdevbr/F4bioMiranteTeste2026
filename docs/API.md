# API

Base URL local: `http://localhost:8123`

## GET /health

Retorna status agregado.

```json
{ "status": "ok", "postgres": "ok", "langfuse": "disabled" }
```

## POST /modernize

Body:

```json
{
  "source_code": "CREATE OR REPLACE FUNCTION ...",
  "schema_sql": "CREATE TABLE ...",
  "procedure_name": "opcional",
  "metadata": {}
}
```

Resposta 200:

```json
{
  "status": "success",
  "generated_code": "...",
  "report": {},
  "history_id": "uuid",
  "run_id": "uuid"
}
```

Erros:

- 422: validação Pydantic
- 500: `{ "detail": { "error": "..." } }`

## GET /evaluation/summary?limit=100

```json
{
  "sample_size": 10,
  "metrics": { "ast_parse_success": 1.0 },
  "raw_count_by_metric": { "ast_parse_success": 10 }
}
```

## Exemplos curl

```bash
curl -s http://localhost:8123/health | jq

curl -s -X POST http://localhost:8123/modernize \
  -H "Content-Type: application/json" \
  -d @- <<'EOF'
{
  "source_code": "CREATE OR REPLACE FUNCTION fn_saldo_cliente(p_cliente_id BIGINT)\nRETURNS NUMERIC(18,2)\nLANGUAGE plpgsql\nAS $$\nDECLARE v_total NUMERIC(18,2);\nBEGIN\n  SELECT COALESCE(SUM(saldo),0) INTO v_total FROM contas WHERE cliente_id=p_cliente_id AND status='ATIVA';\n  RETURN v_total;\nEND;\n$$;"
}
EOF
```
