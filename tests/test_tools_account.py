from supportdesk.tools import ToolContext, ToolRegistry


def test_get_customer_returns_profile(registry: ToolRegistry, ctx: ToolContext) -> None:
    result = registry.run(ctx, "get_customer", {"customer_id": "C-1002"})

    assert not result.is_error
    assert result.content["name"] == "Bob Chen"
    assert result.content["tier"] == "gold"
    assert result.content["loyalty_points"] == 5120


# Go:
#   res := reg.Run(ctx, "get_customer", json.RawMessage(`{"customer_id":"C-1002"}`))
#   if res.IsError { t.Fatalf("unexpected error: %v", res.Content) }
#   if res.Content["name"] != "Bob Chen" { t.Errorf(...) }
# Tests go through the registry, exactly the path the agent loop will use: input
# validation, handler, JSON serialisation.


def test_get_customer_unknown_id(registry: ToolRegistry, ctx: ToolContext) -> None:
    result = registry.run(ctx, "get_customer", {"customer_id": "C-9999"})

    assert result.is_error
    assert result.content["error"] == "customer_not_found"


def test_get_customer_malformed_id(registry: ToolRegistry, ctx: ToolContext) -> None:
    result = registry.run(ctx, "get_customer", {"customer_id": "bob"})

    assert result.is_error
    assert result.content["error"] == "invalid_input"
    assert "customer_id" in str(result.content["message"])


# The message names the bad field, so the model knows what to fix on its next try.


def test_lookup_order_includes_refund_totals(registry: ToolRegistry, ctx: ToolContext) -> None:
    result = registry.run(ctx, "lookup_order", {"order_id": "O-5010"})

    assert not result.is_error
    assert result.content["refunded_total"] == "18.00"
    assert result.content["refundable_amount"] == "64.00"


# Decimals are serialised as strings ("18.00") in JSON mode, so no precision is lost
# on the way to the model. Go's shopspring/decimal marshals the same way by default.


def test_lookup_order_exposes_notes_as_data(registry: ToolRegistry, ctx: ToolContext) -> None:
    result = registry.run(ctx, "lookup_order", {"order_id": "O-5013"})

    order = result.content["order"]
    assert isinstance(order, dict)
    assert "SYSTEM:" in str(order["notes"])


# The prompt-injection fixture (trap #6) must reach the model unchanged; defending
# against it is the agent's and the gates' job, not the data layer's.
# isinstance() narrows the JsonValue union to dict for pyright - like a Go type switch.


def test_lookup_order_unknown_id(registry: ToolRegistry, ctx: ToolContext) -> None:
    result = registry.run(ctx, "lookup_order", {"order_id": "O-0001"})

    assert result.is_error
    assert result.content["error"] == "order_not_found"


def test_lookup_order_rejects_extra_arguments(registry: ToolRegistry, ctx: ToolContext) -> None:
    result = registry.run(ctx, "lookup_order", {"order_id": "O-5001", "include_secrets": True})

    assert result.is_error
    assert result.content["error"] == "invalid_input"


# Go: DisallowUnknownFields again - the model can't smuggle in parameters we don't define.
