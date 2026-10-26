"""The one door to the model. The loop depends on `ModelClient`, never on the SDK class, so
tests can pass a fake that replays scripted responses and never touches the network.
"""

from collections.abc import Sequence
from typing import Protocol

from anthropic import AsyncAnthropic
from anthropic.types import Message, MessageParam, ToolParam

from supportdesk.config import Settings


class ModelClient(Protocol):
    async def create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        messages: Sequence[MessageParam],
        tools: Sequence[ToolParam],
    ) -> Message: ...


# Go:
#   type ModelClient interface {
#       Create(ctx context.Context, req CreateRequest) (*anthropic.Message, error)
#   }
# Deliberately narrow: only the arguments SupportDesk uses. The SDK's own
# messages.create takes ~20 optional parameters; a fake would have to mirror all of them.
# `async def` in a Protocol means "an awaitable method": callers write `await c.create(...)`.
# Errors (network, 429, 5xx) are raised as exceptions, not returned - in Python that is
# the norm; the SDK already retries 429/5xx twice with backoff before raising.


class AnthropicClient:
    def __init__(self, client: AsyncAnthropic) -> None:
        self._client = client

    @classmethod
    def from_settings(cls, settings: Settings) -> "AnthropicClient":
        if settings.anthropic_api_key is None:
            msg = "ANTHROPIC_API_KEY is not set (see .env.example)"
            raise RuntimeError(msg)
        return cls(AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value()))

    async def create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        messages: Sequence[MessageParam],
        tools: Sequence[ToolParam],
    ) -> Message:
        return await self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            tools=tools,
        )


# Go:
#   type AnthropicClient struct{ c anthropic.Client }
#   func (a *AnthropicClient) Create(ctx context.Context, r CreateRequest) (*anthropic.Message,
#       error) {
#       return a.c.Messages.New(ctx, anthropic.MessageNewParams{Model: r.Model, ...})
#   }
# An adapter: the real SDK behind our small interface. It satisfies ModelClient
# structurally - there is no `implements` keyword, just like Go. pyright checks the
# match wherever an AnthropicClient is passed as a ModelClient.
# AsyncAnthropic uses httpx under the hood and is safe to share between requests, so
# create one per process (like an *http.Client), not one per call.
