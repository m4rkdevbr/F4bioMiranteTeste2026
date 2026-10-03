# Development

## Ambiente local

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -e ".[dev]"
cp .env.example .env
```

Subir Postgres:

```bash
docker compose up -d postgres
```

Rodar servidor oficial (LangGraph CLI + custom routes):

```bash
# Postgres
docker compose up -d postgres

# LangGraph CLI (porta 8123; rotas /modernize e /health via http.app)
langgraph dev --host 127.0.0.1 --port 8123
```

Alternativa direta (sem CLI, útil para debug):

```bash
set PYTHONPATH=src
uvicorn modernization_pipeline.api.routes:app --reload --port 8123
```

## Testes

```bash
set PYTHONPATH=src
pytest -q
ruff check src tests scripts
mypy src/modernization_pipeline
```

Testes `@pytest.mark.live` (se adicionados) exigem `OPENROUTER_API_KEY` e não rodam no CI.

## Convenções

- Pacote em `src/modernization_pipeline`
- Mensagens de domínio / docstrings de módulos gerados em PT-BR
- Sem commits de `.env`, caches ou artefatos de IDE
- Prompt versionado em `prompts/generation_system_v1.txt`

## Batch anexos

```bash
python scripts/run_annexes.py
python scripts/run_annexes.py --only anexo_b_fn_saldo_cliente
```
