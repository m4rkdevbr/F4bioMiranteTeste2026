# Observability (Langfuse)

## Objetivo

Rastrear cada execução do pipeline: trace por run, spans/generations das chamadas LLM, latência e scores de evaluation.

## Subir self-hosted (recomendado para o desafio)

```bash
docker compose -f docker-compose.yml -f docker-compose.langfuse.yml up --build -d
```

Isso sobe:

- Postgres da pipeline (`modernization`)
- Postgres do Langfuse + `langfuse/langfuse:2`
- Pipeline com `LANGFUSE_ENABLED=true` e keys de demo

### Acesso

| Item | Valor |
|------|-------|
| UI | http://localhost:3000 |
| Email | `demo@modernization.local` |
| Senha | `demopass123` |
| Public key | `pk-lf-demo-modernization` |
| Secret key | `sk-lf-demo-modernization` |

## Como evidenciar

1. Abra a UI e autentique com o usuário demo.
2. Execute um `POST /modernize` (Swagger em http://localhost:8123/docs).
3. No Langfuse, abra o projeto **Hybrid Pipeline** e inspecione o trace (generation + scores).
4. Capture a tela e salve em `docs/assets/langfuse-traces.png` (referenciada no README).

## Integração no código

- Callback LangChain em `observability/langfuse.py`
- Scores (`ast_parse_success`, `structural_mapping_score`, etc.) enviados após a validação
- `/health` reporta `"langfuse": "ok|disabled|degraded"`
