"""Step executors — the heart of the workflow engine.

Each executor is a **pure async function**: it takes an already-rendered config
(``{{ refs }}`` resolved by the runner) plus an ``ExecContext`` and returns a
``StepResult``. No database access here, so these are trivially unit-testable
with a mocked LLM/HTTP layer.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..enums import StepType
from .llm import LLMError, build_messages, chat_completion

_MAX_BODY_CHARS = 100_000


class StepError(Exception):
    """A step failed in a way that should fail the run (after retries)."""


@dataclass
class ExecContext:
    api_key: str
    base_url: str
    default_model: str
    max_output_tokens: int
    llm_timeout: float
    http_timeout: float


@dataclass
class StepResult:
    output: dict[str, Any]
    logs: list[dict[str, str]] = field(default_factory=list)
    skip_rest: bool = False  # set by a conditional that short-circuits the run


async def execute_step(
    step_type: str, name: str, config: dict[str, Any], ctx: ExecContext
) -> StepResult:
    if step_type == StepType.http_fetch:
        return await _http_fetch(config, ctx)
    if step_type == StepType.llm:
        return await _llm(config, ctx)
    if step_type == StepType.transform:
        return _transform(config)
    if step_type == StepType.conditional:
        return _conditional(config)
    if step_type == StepType.output:
        return _output(config)
    raise StepError(f"unknown step type: {step_type}")


def _truncate(text: str) -> str:
    return text if len(text) <= _MAX_BODY_CHARS else text[:_MAX_BODY_CHARS] + "…[truncated]"


async def _http_fetch(cfg: dict[str, Any], ctx: ExecContext) -> StepResult:
    url = cfg.get("url")
    if not url or not isinstance(url, str):
        raise StepError("http_fetch step requires a string 'url'")
    method = str(cfg.get("method", "GET")).upper()
    headers = cfg.get("headers") or {}
    params = cfg.get("query") or cfg.get("params") or {}
    json_body = cfg.get("json")

    logs = [{"level": "info", "message": f"{method} {url}"}]
    try:
        async with httpx.AsyncClient(timeout=ctx.http_timeout, follow_redirects=True) as client:
            resp = await client.request(method, url, headers=headers, params=params, json=json_body)
    except httpx.HTTPError as exc:
        raise StepError(f"HTTP request failed: {exc}") from exc

    if "application/json" in resp.headers.get("content-type", ""):
        try:
            body: Any = resp.json()
        except (json.JSONDecodeError, ValueError):
            body = _truncate(resp.text)
    else:
        body = _truncate(resp.text)

    logs.append(
        {
            "level": "info" if resp.is_success else "warn",
            "message": f"← {resp.status_code} ({len(resp.content)} bytes)",
        }
    )
    return StepResult(
        output={"status_code": resp.status_code, "ok": resp.is_success, "body": body},
        logs=logs,
    )


async def _llm(cfg: dict[str, Any], ctx: ExecContext) -> StepResult:
    prompt = cfg.get("prompt")
    if prompt is None:
        raise StepError("llm step requires a 'prompt'")
    if not isinstance(prompt, str):
        prompt = json.dumps(prompt)
    system = cfg.get("system")
    if system is not None and not isinstance(system, str):
        system = json.dumps(system)

    model = cfg.get("model") or ctx.default_model
    try:
        temperature = float(cfg.get("temperature", 0.7))
    except (TypeError, ValueError):
        temperature = 0.7
    try:
        requested = int(cfg.get("max_tokens", ctx.max_output_tokens))
    except (TypeError, ValueError):
        requested = ctx.max_output_tokens
    max_tokens = max(1, min(requested, ctx.max_output_tokens))  # hard cap

    try:
        result = await chat_completion(
            api_key=ctx.api_key,
            base_url=ctx.base_url,
            model=model,
            messages=build_messages(prompt, system),
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=ctx.llm_timeout,
        )
    except LLMError as exc:
        raise StepError(str(exc)) from exc

    logs = [{"level": "info", "message": f"model {result.model}"}]
    if result.usage:
        cost = result.cost if result.cost is not None else "?"
        logs.append(
            {
                "level": "info",
                "message": f"tokens={result.usage.get('total_tokens', '?')} cost=${cost}",
            }
        )
    return StepResult(
        output={"content": result.content, "model": result.model, "usage": result.usage},
        logs=logs,
    )


def _transform(cfg: dict[str, Any]) -> StepResult:
    # The runner has already resolved {{ refs }}; transform just packages the
    # reshaped data. Use `template` for an explicit shape, else echo the config.
    result = cfg["template"] if "template" in cfg else {k: v for k, v in cfg.items()}
    return StepResult(output={"result": result}, logs=[{"level": "info", "message": "applied transform"}])


_COMPARATORS = {"==", "!=", ">", "<", ">=", "<=", "contains", "not_contains", "exists"}


def _compare(left: Any, op: str, right: Any) -> bool:
    if op not in _COMPARATORS:
        raise StepError(f"unknown conditional op: {op}")
    try:
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == ">":
            return left > right
        if op == "<":
            return left < right
        if op == ">=":
            return left >= right
        if op == "<=":
            return left <= right
        if op == "contains":
            return right in left
        if op == "not_contains":
            return right not in left
        if op == "exists":
            return left is not None
    except TypeError:
        return False
    return False


def _conditional(cfg: dict[str, Any]) -> StepResult:
    left = cfg.get("left")
    op = str(cfg.get("op", "=="))
    right = cfg.get("right")
    passed = _compare(left, op, right)
    stop = bool(cfg.get("stop_on_false", True)) and not passed
    logs = [{"level": "info", "message": f"{json.dumps(left)} {op} {json.dumps(right)} → {passed}"}]
    if stop:
        logs.append({"level": "info", "message": "condition false; skipping remaining steps"})
    return StepResult(output={"passed": passed}, logs=logs, skip_rest=stop)


def _output(cfg: dict[str, Any]) -> StepResult:
    value = cfg.get("value", {k: v for k, v in cfg.items()})
    return StepResult(output={"result": value}, logs=[{"level": "info", "message": "captured output"}])
