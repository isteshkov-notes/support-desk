"""One place that knows every tool: the agent loop gets definitions and runs tools here."""

from collections.abc import Sequence
from typing import Protocol

from anthropic.types import ToolParam

from supportdesk.tools.account import GET_CUSTOMER, LOOKUP_ORDER
from supportdesk.tools.base import ErrorCode, ToolContext, ToolResult, error_result
from supportdesk.tools.policies import SEARCH_POLICIES
from supportdesk.tools.refunds import ISSUE_REFUND


class RunnableTool(Protocol):
    @property
    def name(self) -> str: ...
    def definition(self) -> ToolParam: ...
    def run(self, ctx: ToolContext, raw_input: object) -> ToolResult: ...


# Go:
#   type RunnableTool interface {
#       Name() string
#       Definition() anthropic.ToolParam
#       Run(ctx ToolContext, raw json.RawMessage) ToolResult
#   }
#
# Why not store Tool[...] directly? Tool[GetCustomerInput] and Tool[IssueRefundInput]
# are different types (like Tool[A] and Tool[B] in Go), so a list of them needs a
# non-generic interface. Same trick as in Go: put the generic type behind an interface
# with no type parameters.


class ToolRegistry:
    def __init__(self, tools: Sequence[RunnableTool]) -> None:
        self._tools: dict[str, RunnableTool] = {}
        for tool in tools:
            if tool.name in self._tools:
                msg = f"duplicate tool name: {tool.name}"
                raise ValueError(msg)
            self._tools[tool.name] = tool

    # Go:
    #   func NewToolRegistry(tools ...RunnableTool) (*ToolRegistry, error) {
    #       m := map[string]RunnableTool{}
    #       for _, t := range tools {
    #           if _, dup := m[t.Name()]; dup {
    #               return nil, fmt.Errorf("duplicate tool name: %s", t.Name())
    #           }
    #           m[t.Name()] = t
    #       }
    #       return &ToolRegistry{tools: m}, nil
    #   }
    # A programming error (two tools with one name) raises: it's caught at startup, not
    # returned to the model. (`msg = ...; raise X(msg)` is a ruff style rule, EM101.)

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    # @property makes a method readable like a field: registry.names, not registry.names().

    def definitions(self) -> list[ToolParam]:
        return [tool.definition() for tool in self._tools.values()]

    # Go:
    #   func (r *ToolRegistry) Definitions() []anthropic.ToolParam
    # Dicts keep insertion order in Python (Go maps don't), so tools are listed in the
    # order they were registered - this matters for prompt caching from week 3.

    def run(self, ctx: ToolContext, name: str, raw_input: object) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            known = ", ".join(self._tools)
            return error_result(
                ErrorCode.UNKNOWN_TOOL, f"No tool named {name!r}. Available: {known}."
            )
        return tool.run(ctx, raw_input)

    # Go:
    #   func (r *ToolRegistry) Run(ctx ToolContext, name string, raw json.RawMessage) ToolResult {
    #       t, ok := r.tools[name]
    #       if !ok { return errResult(UnknownTool, ...) }
    #       return t.Run(ctx, raw)
    #   }
    # {name!r} formats with repr(), i.e. with quotes - like %q in Go.


def default_registry() -> ToolRegistry:
    return ToolRegistry([GET_CUSTOMER, LOOKUP_ORDER, SEARCH_POLICIES, ISSUE_REFUND])


# Go:
#   func DefaultRegistry() *ToolRegistry {
#       return must(NewToolRegistry(
#           GetCustomerTool, LookupOrderTool, SearchPoliciesTool, IssueRefundTool,
#       ))
#   }
