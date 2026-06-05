import pytest

from app.enums import StepType
from app.services import engine as engine_mod
from app.services.engine import ExecContext, StepError, execute_step
from app.services.llm import LLMResult


def _ctx() -> ExecContext:
    return ExecContext(
        api_key="k",
        base_url="http://example.test",
        default_model="test-model",
        max_output_tokens=100,
        llm_timeout=5.0,
        http_timeout=5.0,
    )


async def test_transform_packages_template():
    r = await execute_step(StepType.transform, "t", {"template": {"a": 1}}, _ctx())
    assert r.output == {"result": {"a": 1}}


async def test_output_captures_value():
    r = await execute_step(StepType.output, "o", {"value": {"x": 1}}, _ctx())
    assert r.output == {"result": {"x": 1}}


@pytest.mark.parametrize(
    "cfg,expected",
    [
        ({"left": 5, "op": ">", "right": 3}, True),
        ({"left": "a", "op": "==", "right": "a"}, True),
        ({"left": [1, 2], "op": "contains", "right": 2}, True),
        ({"left": 1, "op": ">", "right": 3}, False),
        ({"left": "x", "op": ">", "right": 3}, False),  # type mismatch -> False, no crash
    ],
)
async def test_conditional_eval(cfg, expected):
    r = await execute_step(StepType.conditional, "c", cfg, _ctx())
    assert r.output["passed"] is expected


async def test_conditional_false_skips_rest():
    r = await execute_step(
        StepType.conditional, "c", {"left": 1, "op": ">", "right": 3, "stop_on_false": True}, _ctx()
    )
    assert r.skip_rest is True


async def test_llm_uses_default_model_and_caps_tokens(monkeypatch):
    captured = {}

    async def fake_chat(**kwargs):
        captured.update(kwargs)
        return LLMResult(content="hello", model=kwargs["model"], usage={"total_tokens": 4}, cost=0.0)

    monkeypatch.setattr(engine_mod, "chat_completion", fake_chat)
    r = await execute_step(StepType.llm, "l", {"prompt": "hi", "max_tokens": 9999}, _ctx())
    assert r.output["content"] == "hello"
    assert captured["model"] == "test-model"
    assert captured["max_tokens"] == 100  # capped to ExecContext.max_output_tokens


async def test_llm_requires_prompt():
    with pytest.raises(StepError):
        await execute_step(StepType.llm, "l", {}, _ctx())


async def test_http_fetch_parses_json(monkeypatch):
    class FakeResp:
        status_code = 200
        headers = {"content-type": "application/json"}
        content = b'{"ok": true}'
        is_success = True

        def json(self):
            return {"ok": True}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, *a, **k):
            return FakeResp()

    monkeypatch.setattr(engine_mod.httpx, "AsyncClient", FakeClient)
    r = await execute_step(StepType.http_fetch, "h", {"url": "http://example.test"}, _ctx())
    assert r.output["status_code"] == 200
    assert r.output["body"] == {"ok": True}


async def test_http_fetch_requires_url():
    with pytest.raises(StepError):
        await execute_step(StepType.http_fetch, "h", {}, _ctx())


async def test_unknown_step_type_raises():
    with pytest.raises(StepError):
        await execute_step("nonsense", "x", {}, _ctx())
