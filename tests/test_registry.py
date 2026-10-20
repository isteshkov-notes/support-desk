import re

import pytest
from anthropic.types import ToolParam
from jsonschema import Draft202012Validator

from supportdesk.tools import ToolContext, ToolRegistry
from supportdesk.tools.account import GET_CUSTOMER

EXPECTED_TOOLS = ["get_customer", "lookup_order", "search_policies", "issue_refund"]
TOOL_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")  # Messages API rule for tool names


def test_registry_lists_the_four_tools_in_order(registry: ToolRegistry) -> None:
    assert registry.names == EXPECTED_TOOLS


@pytest.fixture(params=EXPECTED_TOOLS)
def definition(request: pytest.FixtureRequest, registry: ToolRegistry) -> ToolParam:
    return next(d for d in registry.definitions() if d["name"] == request.param)


# Go:
#   for _, def := range reg.Definitions() { t.Run(def.Name, func(t *testing.T) { ... }) }
# A parametrized *fixture*: every test that asks for `definition` runs once per tool.
# next(generator) = "first match", like a loop with an early return.


def test_definition_has_a_valid_json_schema(definition: ToolParam) -> None:
    schema = definition["input_schema"]
    Draft202012Validator.check_schema(schema)  # raises if the schema itself is invalid
    assert schema.get("type") == "object"
    assert schema.get("additionalProperties") is False


def test_definition_is_usable_by_the_api(definition: ToolParam) -> None:
    assert TOOL_NAME.match(definition["name"])
    description = definition.get("description", "")
    assert len(description) >= 100, "describe what it returns, when to use it, errors"


# A cheap tool-design guard: Anthropic's guidance is that detailed descriptions matter
# more than anything else for tool selection.


def test_unknown_tool_is_an_error_result(registry: ToolRegistry, ctx: ToolContext) -> None:
    result = registry.run(ctx, "delete_all_orders", {})

    assert result.is_error
    assert result.content["error"] == "unknown_tool"
    assert "get_customer" in str(result.content["message"])


def test_duplicate_tool_names_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        ToolRegistry([GET_CUSTOMER, GET_CUSTOMER])


def test_non_object_input_is_rejected(registry: ToolRegistry, ctx: ToolContext) -> None:
    result = registry.run(ctx, "get_customer", "C-1001")

    assert result.content["error"] == "invalid_input"
