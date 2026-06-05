"""Tiny, safe ``{{ reference }}`` templating for passing data between steps.

A workflow step's config can reference the run input and the outputs of earlier
steps, e.g.::

    {{ input.topic }}
    {{ steps.fetch.output.body }}
    {{ steps.fetch.output.items.0.title }}

Resolution rules:
* If a string is *exactly* one ``{{ ... }}`` expression, the resolved value is
  returned with its native type (dict/list/number preserved).
* Otherwise expressions are stringified and interpolated into the text.

No ``eval`` — only attribute/index path lookups against the context dict.
"""
from __future__ import annotations

import json
import re
from typing import Any

_PATTERN = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")


class TemplateError(Exception):
    """Raised when a reference cannot be resolved."""


def _resolve_path(path: str, context: dict[str, Any]) -> Any:
    cur: Any = context
    for raw in path.split("."):
        tok = raw.strip()
        if isinstance(cur, dict):
            if tok not in cur:
                raise TemplateError(f"unknown reference: {{{{ {path} }}}}")
            cur = cur[tok]
        elif isinstance(cur, list):
            try:
                cur = cur[int(tok)]
            except (ValueError, IndexError) as exc:
                raise TemplateError(f"bad list index in: {{{{ {path} }}}}") from exc
        else:
            raise TemplateError(
                f"cannot resolve '{tok}' on {type(cur).__name__} in: {{{{ {path} }}}}"
            )
    return cur


def _render_str(value: str, context: dict[str, Any]) -> Any:
    matches = list(_PATTERN.finditer(value))
    if not matches:
        return value
    # Single, whole-string expression -> preserve native type.
    if len(matches) == 1 and matches[0].group(0).strip() == value.strip():
        return _resolve_path(matches[0].group(1), context)

    def _repl(match: re.Match) -> str:
        resolved = _resolve_path(match.group(1), context)
        return resolved if isinstance(resolved, str) else json.dumps(resolved)

    return _PATTERN.sub(_repl, value)


def render(value: Any, context: dict[str, Any]) -> Any:
    """Recursively render templates inside strings/dicts/lists."""
    if isinstance(value, str):
        return _render_str(value, context)
    if isinstance(value, dict):
        return {k: render(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [render(v, context) for v in value]
    return value
