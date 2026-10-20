"""The building blocks every tool shares: context, results, errors and the Tool wrapper."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from anthropic.types import ToolParam
from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from supportdesk.repository import Repository

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


# Go:
#   func utcNow() time.Time { return time.Now().UTC() }
# datetime.now() without a timezone returns a "naive" time - a classic Python bug.
# Always pass UTC.


@dataclass(frozen=True, slots=True)
class ToolContext:
    repo: Repository
    now: Callable[[], datetime] = field(default=utc_now)


# Go:
#   type ToolContext struct {
#       Repo Repository
#       Now  func() time.Time   // injectable clock, so tests can freeze time
#   }
#
# @dataclass generates __init__, __repr__ and __eq__ from the annotated fields - a
# plain struct without pydantic's validation (use it for internal plumbing; use
# pydantic at trust boundaries: JSON files, HTTP, model output). frozen = immutable,
# slots = fixed fields (no dynamic attributes, less memory) - closest to a Go struct.
# Later phases add the session identity here (customer_id, verified) for the gates.


class ErrorCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    UNKNOWN_TOOL = "unknown_tool"
    CUSTOMER_NOT_FOUND = "customer_not_found"
    ORDER_NOT_FOUND = "order_not_found"
    ORDER_NOT_REFUNDABLE = "order_not_refundable"
    AMOUNT_EXCEEDS_REFUNDABLE = "amount_exceeds_refundable"
    INTERNAL_ERROR = "internal_error"


class ToolError(BaseModel):
    error: ErrorCode
    message: str


# Go:
#   type ToolError struct {
#       Error   ErrorCode `json:"error"`
#       Message string    `json:"message"`
#   }
#
# Tool errors are *data*, not exceptions: the model reads `message` and can recover
# (ask the customer for a correct ID, lower the amount). Write messages for the model:
# say what was wrong and what to do next.


@dataclass(frozen=True, slots=True)
class ToolResult:
    content: dict[str, JsonValue]
    is_error: bool = False


# Go:
#   type ToolResult struct {
#       Content map[string]any `json:"content"`
#       IsError bool           `json:"is_error"`
#   }
# Maps 1:1 to the Messages API `tool_result` block in week 2: content is sent back to
# the model, is_error sets the block's is_error flag.


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Base for every tool's input model. extra="forbid" rejects arguments the model invents,
# and adds "additionalProperties": false to the JSON schema it sees (required later for
# strict tool use).


class Tool[InputT: ToolInput]:
    def __init__(
        self,
        *,
        name: str,
        description: str,
        input_model: type[InputT],
        handler: Callable[[ToolContext, InputT], BaseModel],
    ) -> None:
        self.name = name
        self.description = description
        self.input_model = input_model
        self.handler = handler

    # Go (generics, 1.18+):
    #   type Tool[In any] struct {
    #       Name, Description string
    #       Handler           func(ToolContext, In) (any, *ToolError)
    #   }
    #
    # `class Tool[InputT: ToolInput]` is the 3.12+ generics syntax: InputT is a type
    # parameter bounded by ToolInput (like [In ToolInput] if ToolInput were an
    # interface). `type[InputT]` means "the class itself", not an instance - Go has no
    # direct equivalent; you'd pass a zero value or reflect.Type.
    # The bare `*` makes every argument keyword-only: Tool(name=..., ...).

    def definition(self) -> ToolParam:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
        }

    # Go:
    #   func (t Tool[In]) Definition() anthropic.ToolParam {
    #       return anthropic.ToolParam{Name: t.Name, Description: ..., InputSchema: schemaOf[In]()}
    #   }
    # This is what Claude sees. ToolParam is a TypedDict - a dict with a fixed set of
    # typed keys (pyright checks the keys; at runtime it's a plain dict). The JSON
    # schema is generated from the pydantic model, so the schema the model sees and the
    # validation we run can never drift apart.

    def run(self, ctx: ToolContext, raw_input: object) -> ToolResult:
        try:
            args = self.input_model.model_validate(raw_input)
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(map(str, err['loc'])) or 'input'}: {err['msg']}" for err in exc.errors()
            )
            return error_result(
                ErrorCode.INVALID_INPUT, f"Invalid arguments for {self.name}: {problems}"
            )

        try:
            result = self.handler(ctx, args)
        except Exception:  # tool boundary: never let an exception escape into the agent loop
            logger.exception("tool %s crashed", self.name)
            return error_result(
                ErrorCode.INTERNAL_ERROR, f"{self.name} failed unexpectedly. Try later."
            )

        return ToolResult(
            content=result.model_dump(mode="json"),
            is_error=isinstance(result, ToolError),
        )

    # Go:
    #   func (t Tool[In]) Run(ctx ToolContext, raw json.RawMessage) ToolResult {
    #       var in In
    #       if err := json.Unmarshal(raw, &in); err != nil { return errResult(...) }
    #       if err := in.Validate(); err != nil { return errResult(...) }
    #       out, err := func() (out any, err error) {
    #           defer func() { if r := recover(); r != nil { err = fmt.Errorf("%v", r) } }()
    #           return t.Handler(ctx, in)
    #       }()
    #       ...
    #   }
    #
    # `except Exception` is Go's recover(): a bug in one tool becomes an error result,
    # not a crashed request. logger.exception logs the full traceback.
    # model_dump(mode="json") converts Decimal/datetime/enums to JSON-safe str/str/str.
    # isinstance(x, T) is a Go type assertion: _, ok := x.(*ToolError).


def error_result(code: ErrorCode, message: str) -> ToolResult:
    return ToolResult(
        content=ToolError(error=code, message=message).model_dump(mode="json"), is_error=True
    )


# Go:
#   func errResult(code ErrorCode, msg string) ToolResult
# Shared by Tool.run and the registry (unknown tool name).
