"""Langfuse observability helpers (optional, free self-hosted)."""

from __future__ import annotations

import logging
from typing import Any

from modernization_pipeline.config import get_settings

logger = logging.getLogger(__name__)


def langfuse_enabled() -> bool:
    settings = get_settings()
    return bool(
        settings.langfuse_enabled
        and settings.langfuse_public_key
        and settings.langfuse_secret_key
    )


def get_langfuse_client() -> Any | None:
    if not langfuse_enabled():
        return None
    try:
        from langfuse import Langfuse

        settings = get_settings()
        return Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Langfuse client unavailable: %s", exc)
        return None


def get_langchain_handler() -> Any | None:
    if not langfuse_enabled():
        return None
    try:
        from langfuse.callback import CallbackHandler

        settings = get_settings()
        return CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Langfuse callback unavailable: %s", exc)
        return None


def score_run(
    *,
    trace_id: str | None,
    scores: dict[str, float],
    comment: str | None = None,
) -> None:
    client = get_langfuse_client()
    if client is None or not trace_id:
        return
    try:
        for name, value in scores.items():
            client.score(trace_id=trace_id, name=name, value=value, comment=comment)
        client.flush()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to push Langfuse scores: %s", exc)


def check_langfuse() -> str:
    if not langfuse_enabled():
        return "disabled"
    client = get_langfuse_client()
    return "ok" if client is not None else "degraded"
