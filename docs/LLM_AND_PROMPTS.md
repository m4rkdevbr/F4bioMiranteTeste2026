# LLM and prompts

## Provider

- Gateway: **OpenRouter**
- Endpoint: `https://openrouter.ai/api/v1/chat/completions`
- Client: `langchain_openai.ChatOpenAI` com `base_url` OpenRouter

## Free model chain

1. `qwen/qwen3.8-27b:free` (primary)
2. `nvidia/nemotron-3-super-120b-a12b:free`
3. `google/gemma-4-31b-it:free`
4. `cohere/north-mini-code:free`
5. `openrouter/free`

Em 429/5xx/erro de provider, avança na cadeia. O `report.generation` registra `model_used`, `attempts` e `fallback_triggered`.

## Construção de contexto

O LLM **não** recebe apenas a procedure bruta. O user prompt é JSON contendo:

- `parsed_ir` (nome, params, body, fragments SQL, constructs)
- `semantic_profile` (risk_flags, translation_hints, strategy)
- `schema_sql` opcional (Anexo A)
- `source_code` (referência completa)
- `validation_feedback` em retries

System prompt versionado: `prompts/generation_system_v1.txt`.

## Headers OpenRouter

- `HTTP-Referer`: URL do repositório
- `X-Title`: Modernization Pipeline

## Segurança

Chave apenas em `.env` (gitignored). Nunca em README, fixtures ou CI logs.
