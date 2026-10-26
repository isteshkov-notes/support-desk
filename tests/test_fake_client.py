from typing import TYPE_CHECKING

import pytest

from tests.fakes import FakeClient, reply, text, tool_use

if TYPE_CHECKING:
    from anthropic.types import MessageParam


def test_reply_infers_stop_reason() -> None:
    assert reply(text("Done.")).stop_reason == "end_turn"
    assert reply(text("Let me check."), tool_use("lookup_order", {})).stop_reason == "tool_use"
    assert reply(text("Cut"), stop_reason="max_tokens").stop_reason == "max_tokens"


# The second case is the premature-exit trap in miniature: text AND tool_use in one
# response, and the stop_reason says "tool_use", so the turn is not over.


async def test_fake_replays_responses_and_records_calls() -> None:
    first, second = reply(text("one")), reply(text("two"))
    fake = FakeClient([first, second])
    history: list[MessageParam] = [{"role": "user", "content": "hi"}]

    got_first = await fake.create(model="m", max_tokens=10, system="s", messages=history, tools=[])
    history.append({"role": "assistant", "content": "one"})
    got_second = await fake.create(model="m", max_tokens=10, system="s", messages=history, tools=[])

    assert (got_first, got_second) == (first, second)
    assert len(fake.calls[0].messages) == 1  # a snapshot, not the list that kept growing
    assert len(fake.calls[1].messages) == 2


# Go: an async test is just a normal test; here pytest-asyncio (asyncio_mode = "auto")
# runs each `async def test_*` on a fresh event loop.


async def test_fake_fails_when_the_script_runs_out() -> None:
    fake = FakeClient([])

    with pytest.raises(AssertionError, match="only 0 scripted"):
        await fake.create(model="m", max_tokens=10, system="s", messages=[], tools=[])
