# Observability (Langfuse)

## Objetivo

Rastrear cada execução do pipeline: trace por run, spans por nó (via callbacks LangChain/LangGraph), custo/latência das gerações quando o provider reporta.

## Configuração

No `.env`:

```
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=http://localhost:3000
```

Com `LANGFUSE_ENABLED=false` (default), a pipeline funciona normalmente e `/health` reporta `"langfuse": "disabled"`.

## Self-hosted

Recomenda-se o compose oficial Langfuse (versão atual do projeto). Aponte `LANGFUSE_HOST` para o serviço e reinicie o container `pipeline`.

## Evidência para entrega

Após uma execução `/modernize` ou `scripts/run_annexes.py`, capture a tela de traces e salve em:

`docs/assets/langfuse-traces.png`

Referencie a imagem no README.

## Scores

Após validação, métricas `ast_parse_success`, `structural_mapping_score`, etc. são enviadas ao Langfuse quando o client está ativo.
