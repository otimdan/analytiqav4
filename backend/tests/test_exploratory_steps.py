"""Step-budget behaviour of the exploratory regime.

Covers what a user hits when an open-ended ask ("help me analyse my data")
outruns MAX_STEPS: the analysis has run, but the model never got to write it up.
Uses asyncio.run rather than pytest-asyncio marks, since the suite has no
asyncio_mode configured.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.regimes import exploratory


class _FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, exclude_none=False):
        return {"role": "assistant", "content": self.content}


def _tool_call(code="print(1)"):
    return SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name="execute_code", arguments=json.dumps({"code": code})),
    )


@pytest.fixture
def stub_env(monkeypatch):
    """Neutralise sandbox, DB and context so only the loop is under test."""
    monkeypatch.setattr(exploratory, "get_or_create_sandbox", _async_return("sbx"))
    monkeypatch.setattr(exploratory, "format_context_for_prompt", lambda ctx: "")
    monkeypatch.setattr(exploratory, "run_db", _async_return({"columns": {"age": {}}}))
    monkeypatch.setattr(
        exploratory,
        "execute_code",
        _async_return({"success": True, "stdout": "42", "stderr": "", "images": []}),
    )
    monkeypatch.setattr(exploratory, "build_tool_result_string", lambda r: "42")
    monkeypatch.setattr(exploratory, "MAX_STEPS", 3)


def _async_return(value):
    async def _fn(*args, **kwargs):
        return value

    return _fn


def _run(message="please help me analyze my data", **kwargs):
    return asyncio.run(
        exploratory.handle(
            message=message,
            session=SimpleNamespace(id="s1"),
            context={"recent_turns": [], "mode": "explore"},
            recent_messages=[],
            **kwargs,
        )
    )


def test_exhausted_budget_synthesises_an_answer(stub_env, monkeypatch):
    """The old behaviour apologised and dumped raw code; now it must answer."""
    calls = []

    async def fake_model(**kwargs):
        calls.append(kwargs)
        # Never stops calling tools on its own -> budget runs out.
        if kwargs.get("tools") is None:
            return SimpleNamespace(message=_FakeMessage(content="Age drives the outcome."))
        return SimpleNamespace(message=_FakeMessage(tool_calls=[_tool_call()]))

    monkeypatch.setattr(exploratory, "call_main_model", fake_model)
    result = _run()

    assert result["text"] == "Age drives the outcome."
    assert "maximum number of steps" not in result["text"]
    # The synthesis call must withhold tools, or the model just explores again.
    assert calls[-1]["tools"] is None


def test_wrap_up_nudge_is_injected_before_the_wall(stub_env, monkeypatch):
    """The model can't budget for a limit it can't see."""
    seen = []

    async def fake_model(**kwargs):
        seen.append(kwargs["messages"])
        if kwargs.get("tools") is None:
            return SimpleNamespace(message=_FakeMessage(content="done"))
        return SimpleNamespace(message=_FakeMessage(tool_calls=[_tool_call()]))

    monkeypatch.setattr(exploratory, "call_main_model", fake_model)
    _run()

    nudged = any(
        m.get("content") == exploratory._WRAP_UP_NUDGE
        for convo in seen
        for m in convo
        if isinstance(m, dict)
    )
    assert nudged


def test_clean_answer_skips_synthesis(stub_env, monkeypatch):
    """A model that finishes early must not trigger a second billed call."""
    call_count = 0

    async def fake_model(**kwargs):
        nonlocal call_count
        call_count += 1
        return SimpleNamespace(message=_FakeMessage(content="Mean age is 42."))

    monkeypatch.setattr(exploratory, "call_main_model", fake_model)
    result = _run()

    assert result["text"] == "Mean age is 42."
    assert call_count == 1


def test_empty_final_content_still_gets_a_synthesis_attempt(stub_env, monkeypatch):
    """A model can stop calling tools while returning no content — common in a
    long, output-heavy session. That used to skip synthesis entirely and fall
    straight to the apology, which is what a real user hit at 6 of 10 steps."""
    calls = []

    async def fake_model(**kwargs):
        calls.append(kwargs)
        if kwargs.get("tools") is None:
            return SimpleNamespace(message=_FakeMessage(content="Pooled mortality was 10.7%."))
        return SimpleNamespace(message=_FakeMessage(content=""))

    monkeypatch.setattr(exploratory, "call_main_model", fake_model)
    result = _run()

    assert result["text"] == "Pooled mortality was 10.7%."
    assert calls[-1]["tools"] is None
    assert "couldn't put together" not in result["text"]


def test_missing_chart_on_an_explicit_plot_request_is_retried(stub_env, monkeypatch):
    """Long wrangling sessions routinely end with the plot forgotten."""
    sent = []

    async def fake_model(**kwargs):
        sent.append(kwargs["messages"])
        return SimpleNamespace(message=_FakeMessage(content="Here is the analysis."))

    monkeypatch.setattr(exploratory, "call_main_model", fake_model)
    _run(message="produce a forest plot")

    retried = any(
        m.get("content") == exploratory._CHART_RETRY_PROMPT
        for convo in sent
        for m in convo
        if isinstance(m, dict)
    )
    assert retried


def test_no_chart_retry_when_no_chart_was_asked_for(stub_env, monkeypatch):
    """The retry costs an LLM call plus a sandbox run — it must not fire blind."""
    sent = []

    async def fake_model(**kwargs):
        sent.append(kwargs["messages"])
        return SimpleNamespace(message=_FakeMessage(content="Mean age is 42."))

    monkeypatch.setattr(exploratory, "call_main_model", fake_model)
    _run(message="what is the mean age")

    retried = any(
        m.get("content") == exploratory._CHART_RETRY_PROMPT
        for convo in sent
        for m in convo
        if isinstance(m, dict)
    )
    assert not retried


def test_meta_analysis_is_badged_as_unverified(stub_env, monkeypatch):
    """A pooled estimate reads more authoritative than a hand-written one is."""

    async def fake_model(**kwargs):
        return SimpleNamespace(message=_FakeMessage(content="Pooled mortality 10.7%."))

    monkeypatch.setattr(exploratory, "call_main_model", fake_model)
    result = _run(message="produce a forest plot of in-hospital mortality")

    assert result["test_display_name"] == "Exploratory model (not verified)"
    assert result["engine_verified"] is False
    assert "not from the verified test library" in result["text"]
