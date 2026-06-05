"""Provider-agnostic LLM client.

We call OpenRouter's OpenAI-compatible ``/chat/completions`` endpoint. Because
OpenRouter routes to many providers by model id, the *same* code path reaches
both OpenAI (``openai/gpt-4o-mini``) and Anthropic (``anthropic/claude-3.5-haiku``)
models — exactly what the product needs.

The API key is never logged.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from ..logging_config import get_logger

log = get_logger("llm")


class LLMError(Exception):
    """A non-recoverable error talking to the LLM provider."""


@dataclass
class LLMResult:
    content: str
    model: str
    usage: dict[str, Any]
    cost: float | None


def build_messages(prompt: str, system: str | None = None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


async def chat_completion(
    *,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float = 0.7,
    timeout: float = 60.0,
) -> LLMResult:
    if not api_key:
        raise LLMError("no API key configured for this run")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # OpenRouter attribution headers (recommended).
        "HTTP-Referer": "https://cascade-ai.app",
        "X-Title": "Cascade",
    }
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
    except httpx.HTTPError as exc:
        raise LLMError(f"request to LLM provider failed: {exc}") from exc

    if resp.status_code != 200:
        # Surface the provider's error message, but never the key.
        detail = resp.text[:500]
        log.warning("llm_non_200", status=resp.status_code, model=model)
        raise LLMError(f"LLM provider returned {resp.status_code}: {detail}")

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"unexpected LLM response shape: {str(data)[:300]}") from exc

    usage = data.get("usage", {}) or {}
    return LLMResult(
        content=content or "",
        model=data.get("model", model),
        usage=usage,
        cost=usage.get("cost"),
    )
