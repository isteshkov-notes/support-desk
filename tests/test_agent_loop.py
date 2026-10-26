"""Tests for run_agent_loop. The first one is an example; the rest are YOUR HALF.

While run_agent_loop raises NotImplementedError these are expected failures (xfail). Once
the loop works they pass, and strict xfail turns that into a failure on purpose: delete
the `pytestmark` line below at that point.
"""

import pytest
from anthropic.types import MessageParam

from supportdesk.agent import run_agent_loop
from supportdesk.tools import ToolContext, ToolRegistry
from tests.fakes import FakeClient, reply, text, tool_results, tool_use

pytestmark = pytest.mark.xfail(raises=NotImplementedError, reason="run_agent_loop: TODO")

QUESTION: list[MessageParam] = [{"role": "user", "content": "Where is order O-5003?"}]


async def test_tool_round_trip_then_answer(registry: ToolRegistry, ctx: ToolContext) -> None:
    fake = FakeClient(
        [
            reply(tool_use("lookup_order", {"order_id": "O-5003"}, id_="toolu_1")),
            reply(text("Your order O-5003 has shipped.")),
        ]
    )

    result = await run_agent_loop(
        fake, QUESTION, registry, ctx, model="m", system="s", max_iterations=5
    )

    assert result.text == "Your order O-5003 has shipped."
    assert result.stop_reason == "end_turn"
    assert result.iterations == 2

    # What the model saw on the 2nd call: question, its own tool_use, then our result.
    second_call = fake.calls[1].messages
    assert [m["role"] for m in second_call] == ["user", "assistant", "user"]
    [result_block] = tool_results(second_call[2])
    assert result_block["tool_use_id"] == "toolu_1"
    assert not result_block.get("is_error", False)
    assert "shipped" in str(result_block.get("content"))


# Go:
#   fake := &FakeClient{Responses: []*anthropic.Message{toolUse(...), reply(...)}}
#   res, err := RunAgentLoop(ctx, fake, question, reg, tctx, opts)
#   if res.Iterations != 2 { t.Fatalf(...) }
# `registry` and `ctx` come from conftest.py: the real four tools over fresh fixture data.


# TODO(you): write these, same style as above.
#
# test_text_plus_tool_use_does_not_exit_early
#   One response with text("Let me check that.") AND a tool_use, then a final answer.
#   Assert 2 iterations and the final text - not "Let me check that.".
#
# test_several_tool_uses_in_one_turn_all_get_results
#   One response with 2 tool_use blocks (e.g. lookup_order and get_customer).
#   Assert the 2nd call got ONE user message with TWO tool_result blocks, ids matching.
#
# test_tool_error_is_sent_back_with_is_error
#   tool_use("lookup_order", {"order_id": "O-0000"}): the result block has is_error=True
#   and the loop continues to the next response.
#
# test_iteration_cap
#   max_iterations=3 and a script of tool_use responses only: stop_reason ==
#   "max_iterations", exactly 3 calls made.
#
# test_max_tokens_and_refusal_stop_the_loop  (parametrize over both)
#
# test_callers_messages_are_not_mutated
