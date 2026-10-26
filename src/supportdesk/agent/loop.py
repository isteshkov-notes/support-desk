"""The agent loop, hand-written on the Messages API (SD Phase 2).

YOUR HALF. The types and the signature are fixed; the body is yours. The tests in
tests/test_agent_loop.py tell you when it's right.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from anthropic.types import Message, MessageParam

from supportdesk.agent.client import ModelClient
from supportdesk.tools import ToolContext, ToolRegistry

type StopReason = Literal[
    "end_turn",  # the model finished its answer
    "max_tokens",  # the answer was cut off by max_tokens
    "refusal",  # the model declined to answer
    "max_iterations",  # OUR cap: the loop gave up, see max_iterations
]


@dataclass(frozen=True, slots=True)
class AgentResult:
    text: str  # the final answer: all text blocks of the last response, joined
    stop_reason: StopReason
    iterations: int  # how many times the model was called
    messages: list[MessageParam]  # the full conversation, including every tool round trip
    responses: list[Message]  # every raw response, in order (token/cost logging reads these)


# Go:
#   type AgentResult struct {
#       Text       string
#       StopReason StopReason
#       Iterations int
#       Messages   []anthropic.MessageParam
#       Responses  []*anthropic.Message
#   }
# `type StopReason = Literal[...]` is a 3.12 type alias: a string that may only be one of
# these values (a Go `type StopReason string` plus consts, but checked by pyright).


async def run_agent_loop(  # noqa: PLR0913 - the loop genuinely has this many inputs
    client: ModelClient,
    messages: Sequence[MessageParam],
    registry: ToolRegistry,
    ctx: ToolContext,
    *,
    model: str,
    system: str,
    max_iterations: int,
    max_tokens: int = 1024,
) -> AgentResult:
    # TODO(you): implement. One iteration = one call to client.create(...).
    #
    #  1. Copy `messages` into a new list (don't mutate the caller's list).
    #  2. Call the model with the history and registry.definitions().
    #  3. Append the assistant turn to the history: {"role": "assistant", "content": ...}.
    #     The SDK accepts the response's content blocks as they are.
    #  4. Branch on response.stop_reason:
    #       "tool_use"   -> run EVERY tool_use block in response.content through
    #                       registry.run(ctx, block.name, block.input). Send them all back
    #                       in ONE user message: a list of tool_result blocks, each with
    #                       tool_use_id, content (a string: json.dumps the result) and
    #                       is_error. Then loop.
    #       "pause_turn" -> the server paused a long turn: loop again with the history
    #                       as it is (nothing to add).
    #       "end_turn" / "max_tokens" / "refusal" -> stop, return the result.
    #       anything else -> decide: stop or raise? Write down why.
    #  5. After max_iterations calls without an end, stop with "max_iterations".
    #
    # Traps the tests check:
    #   - a response can contain text AND tool_use. Decide by stop_reason, not by
    #     "is there text?" - otherwise you exit early with a half answer.
    #   - every tool_use id needs exactly one tool_result, or the API returns 400.
    #   - tool results go in a "user" message; tool_result blocks come first in it.
    raise NotImplementedError


# Go:
#   func RunAgentLoop(ctx context.Context, c ModelClient, msgs []anthropic.MessageParam,
#       reg *ToolRegistry, tctx ToolContext, opts LoopOptions) (AgentResult, error)
# `async def` + `await client.create(...)`: while waiting for the HTTP response this
# coroutine is parked and the event loop runs other requests - like a goroutine
# blocked on I/O, except the switch only happens at `await`.
# The registry calls are synchronous (plain `def`): fine, they're in-memory and fast.
