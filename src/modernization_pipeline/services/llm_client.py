"""OpenRouter chat client with free-model fallback chain."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from modernization_pipeline.config import Settings, get_settings

logger = logging.getLogger(__name__)


class LLMGenerationError(RuntimeError):
    def __init__(self, message: str, attempts: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.attempts = attempts


def _build_chat_model(settings: Settings, model: str) -> Any:
    return ChatOpenAI(
        model=model,
        api_key=SecretStr(settings.openrouter_api_key or "missing-key"),
        base_url=settings.openrouter_base_url,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,
        default_headers={
            "HTTP-Referer": settings.openrouter_http_referer,
            "X-Title": settings.openrouter_app_title,
        },
    ).bind(max_tokens=settings.llm_max_tokens)


def generate_with_fallback(
    *,
    system_prompt: str,
    user_prompt: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Call OpenRouter models in chain order until one succeeds."""
    cfg = settings or get_settings()
    if not cfg.openrouter_api_key:
        raise LLMGenerationError(
            "OPENROUTER_API_KEY is not configured",
            attempts=[],
        )

    attempts: list[dict[str, Any]] = []
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    for model in cfg.model_chain:
        attempt: dict[str, Any] = {"model": model, "ok": False}
        try:
            llm = _build_chat_model(cfg, model)
            response = llm.invoke(messages)
            content = getattr(response, "content", "")
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, str):
                        parts.append(block)
                    elif isinstance(block, dict) and "text" in block:
                        parts.append(str(block["text"]))
                content = "".join(parts)
            text = str(content).strip()
            if not text:
                raise RuntimeError("Empty model response")
            attempt["ok"] = True
            attempts.append(attempt)
            return {
                "content": text,
                "model_used": model,
                "attempts": attempts,
                "fallback_triggered": len(attempts) > 1,
            }
        except Exception as exc:  # noqa: BLE001 - capture per-model failure for report
            attempt["error"] = str(exc)
            attempts.append(attempt)
            logger.warning("OpenRouter model %s failed: %s", model, exc)
            continue

    raise LLMGenerationError(
        "All OpenRouter free models in the chain failed",
        attempts=attempts,
    )
