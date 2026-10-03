FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md langgraph.json ./
COPY src ./src
COPY prompts ./prompts
COPY sql ./sql
COPY scripts ./scripts

RUN pip install --upgrade pip \
    && pip install -e ".[dev]" \
    && python -c "import langgraph_runtime_inmem, langgraph_api; print(langgraph_api.__version__)"

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8123

# Official LangGraph CLI local server with custom routes from langgraph.json (http.app)
CMD ["langgraph", "dev", "--host", "0.0.0.0", "--port", "8123", "--no-browser", "--no-reload"]
