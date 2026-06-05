"""Seed the public sample workflow (idempotent).

The sample chains real external calls so the landing-page "try it" button shows
the whole engine working in one click:

    fetch top HN story ids  ->  fetch story #0 details  ->  LLM hot-take  ->  output

Run standalone with:  ``python -m app.seed``
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from .db import SessionLocal
from .enums import StepType
from .logging_config import configure_logging, get_logger
from .models import Org, Workflow, WorkflowStep

log = get_logger("seed")

_DEMO_SLUG = "cascade-demo"

# (type, name, config). Steps reference earlier outputs via {{ ... }} templating.
_SAMPLE_STEPS = [
    (
        StepType.http_fetch,
        "fetch_top",
        {"method": "GET", "url": "https://hacker-news.firebaseio.com/v0/topstories.json"},
    ),
    (
        StepType.http_fetch,
        "fetch_story",
        {
            "method": "GET",
            "url": "https://hacker-news.firebaseio.com/v0/item/{{ steps.fetch_top.output.body.0 }}.json",
        },
    ),
    (
        StepType.llm,
        "hot_take",
        {
            "system": "You write a single punchy, {{ input.tone }} one-liner. One sentence, no preamble.",
            "prompt": (
                "Give your take on this Hacker News story titled: "
                '"{{ steps.fetch_story.output.body.title }}" '
                "(score {{ steps.fetch_story.output.body.score }})."
            ),
            "max_tokens": 80,
        },
    ),
    (
        StepType.output,
        "result",
        {
            "value": {
                "headline": "{{ steps.fetch_story.output.body.title }}",
                "url": "{{ steps.fetch_story.output.body.url }}",
                "score": "{{ steps.fetch_story.output.body.score }}",
                "hot_take": "{{ steps.hot_take.output.content }}",
            }
        },
    ),
]


async def seed_sample_workflow() -> None:
    async with SessionLocal() as session:
        if (await session.execute(select(Workflow.id).where(Workflow.is_sample.is_(True)))).first():
            log.info("sample_already_seeded")
            return

        org = (
            await session.execute(select(Org).where(Org.slug == _DEMO_SLUG))
        ).scalar_one_or_none()
        if org is None:
            org = Org(name="Cascade Demo", slug=_DEMO_SLUG)
            session.add(org)
            await session.flush()

        wf = Workflow(
            org_id=org.id,
            name="HN Hot-Take",
            description=(
                "Fetches the current top Hacker News story and writes a one-line take with an LLM. "
                "Shows an external API call, data passed between steps, and a model call in one run."
            ),
            is_sample=True,
        )
        session.add(wf)
        await session.flush()
        for i, (step_type, name, config) in enumerate(_SAMPLE_STEPS):
            session.add(
                WorkflowStep(workflow_id=wf.id, position=i, type=step_type, name=name, config=config)
            )
        await session.commit()
        log.info("sample_seeded", workflow_id=str(wf.id))


if __name__ == "__main__":
    configure_logging()
    asyncio.run(seed_sample_workflow())
