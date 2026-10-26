"""Test doubles for the model: build scripted responses and replay them in order."""

import copy
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import count

from anthropic.types import (
    Message,
    MessageParam,
    TextBlock,
    ToolParam,
    ToolResultBlockParam,
    ToolUseBlock,
    Usage,
)

type Block = TextBlock | ToolUseBlock

_ids = count(1)


def text(value: str) -> TextBlock:
    return TextBlock(type="text", text=value)


def tool_use(name: str, tool_input: dict[str, object], *, id_: str | None = None) -> ToolUseBlock:
    return ToolUseBlock(
        type="tool_use", id=id_ or f"toolu_{next(_ids):04d}", name=name, input=tool_input
    )


def reply(
    *blocks: Block,
    stop_reason: str | None = None,
    input_tokens: int = 100,
    output_tokens: int = 20,
) -> Message:
    if stop_reason is None:
        stop_reason = "tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn"
    return Message.model_validate(
        {
            "id": f"msg_{next(_ids):04d}",
            "type": "message",
            "role": "assistant",
            "model": "claude-fake",
            "content": [b.model_dump() for b in blocks],
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": Usage(input_tokens=input_tokens, output_tokens=output_tokens).model_dump(),
        }
    )


# Go:
#   func Reply(stopReason string, blocks ...anthropic.ContentBlockUnion) *anthropic.Message
# Builders keep the tests short: reply(text("Checking."), tool_use("lookup_order", {...}))
# reads like the conversation. stop_reason defaults to what the real API would send, and
# can be overridden to script odd cases (max_tokens, pause_turn, refusal).
# model_validate (not the constructor) because content is a discriminated union: pydantic
# picks TextBlock or ToolUseBlock from each dict's "type", exactly as when parsing the API.


@dataclass(frozen=True, slots=True)
class Call:
    model: str
    max_tokens: int
    system: str
    messages: list[MessageParam]
    tools: list[ToolParam]


@dataclass
class FakeClient:
    responses: list[Message]
    calls: list[Call] = field(default_factory=list[Call])

    async def create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        messages: Sequence[MessageParam],
        tools: Sequence[ToolParam],
    ) -> Message:
        self.calls.append(
            Call(model, max_tokens, system, copy.deepcopy(list(messages)), list(tools))
        )
        if len(self.calls) > len(self.responses):
            msg = f"the loop made call #{len(self.calls)}, only {len(self.responses)} scripted"
            raise AssertionError(msg)
        return self.responses[len(self.calls) - 1]


# Go:
#   type FakeClient struct {
#       Responses []*anthropic.Message
#       Calls     []CreateRequest
#   }
#   func (f *FakeClient) Create(_ context.Context, r CreateRequest) (*anthropic.Message, error) {
#       f.Calls = append(f.Calls, r)
#       ...
#   }
# Satisfies ModelClient structurally, like the real AnthropicClient.
# deepcopy matters: the loop keeps appending to the same history list. Without a copy,
# every recorded call would show the FINAL history, and you couldn't assert what the
# model saw on call #2. (Go slices share their backing array - same trap.)
# Running out of scripted responses fails the test loudly instead of hanging or looping.


def tool_results(message: MessageParam) -> list[ToolResultBlockParam]:
    assert message["role"] == "user", "tool results must be sent in a user message"
    content = message["content"]
    assert not isinstance(content, str), "expected a list of tool_result blocks, got a string"
    results: list[ToolResultBlockParam] = []
    for block in content:
        assert isinstance(block, dict), f"expected a dict block, got {block!r}"
        assert block["type"] == "tool_result", f"expected tool_result, got {block['type']}"
        results.append(block)
    return results


# Go:
#   func toolResults(t *testing.T, m anthropic.MessageParam) []anthropic.ToolResultBlockParam
# MessageParam.content is "str | list of ~25 block types", so a test can't index into it
# directly - pyright (rightly) asks "which type is it?". This helper answers once:
# isinstance(block, dict) narrows away the SDK's pydantic block classes, and
# block["type"] == "tool_result" narrows the remaining TypedDict union to
# ToolResultBlockParam (pyright narrows on a Literal "tag" field, like a Go type switch).
# Use it in your tests: tool_results(fake.calls[1].messages[2]).
