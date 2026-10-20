from decimal import Decimal

import pytest
from pydantic import BaseModel

from supportdesk.repository import InMemoryRepository, refunded_total
from supportdesk.tools import Tool, ToolContext, ToolRegistry
from supportdesk.tools.base import ToolInput
from tests.conftest import FIXED_NOW


def test_refund_is_recorded(
    registry: ToolRegistry, ctx: ToolContext, repo: InMemoryRepository
) -> None:
    result = registry.run(
        ctx,
        "issue_refund",
        {"order_id": "O-5010", "amount": "12.5", "reason": "Backpack strap tore."},
    )

    assert not result.is_error
    assert result.content == {
        "id": "R-9003",
        "order_id": "O-5010",
        "amount": "12.50",
        "reason": "Backpack strap tore.",
        "status": "issued",
        "created_at": FIXED_NOW.isoformat().replace("+00:00", "Z"),
    }
    assert refunded_total(repo, "O-5010") == Decimal("30.50")


# Go:
#   want := map[string]any{"id": "R-9003", ...}
#   if diff := cmp.Diff(want, res.Content); diff != "" {
#       t.Errorf("mismatch (-want +got):\n%s", diff)
#   }
# Comparing the whole dict pins the exact JSON the model will see. The frozen clock
# (FIXED_NOW) makes created_at deterministic.


def test_refund_of_exactly_the_remaining_amount_is_allowed(
    registry: ToolRegistry, ctx: ToolContext
) -> None:
    result = registry.run(
        ctx, "issue_refund", {"order_id": "O-5010", "amount": 64, "reason": "Full return."}
    )

    assert not result.is_error


def test_returned_order_can_be_refunded(registry: ToolRegistry, ctx: ToolContext) -> None:
    result = registry.run(
        ctx, "issue_refund", {"order_id": "O-5012", "amount": 149, "reason": "Jacket returned."}
    )

    assert not result.is_error


def test_second_refund_sees_the_first(registry: ToolRegistry, ctx: ToolContext) -> None:
    args = {"order_id": "O-5005", "amount": 30, "reason": "One mat damaged."}

    first = registry.run(ctx, "issue_refund", args)
    second = registry.run(ctx, "issue_refund", args)

    assert not first.is_error
    assert second.content["error"] == "amount_exceeds_refundable"
    assert "20.00" in str(second.content["message"])


# 50.00 total - 30.00 refunded = 20.00 left; the error tells the model the real limit.


@pytest.mark.parametrize(
    ("args", "error"),
    [
        pytest.param(
            {"order_id": "O-0001", "amount": 10, "reason": "x" * 5},
            "order_not_found",
            id="unknown-order",
        ),
        pytest.param(
            {"order_id": "O-5006", "amount": 10, "reason": "Changed mind."},
            "order_not_refundable",
            id="placed",
        ),
        pytest.param(
            {"order_id": "O-5003", "amount": 10, "reason": "Not here yet."},
            "order_not_refundable",
            id="shipped",
        ),
        pytest.param(
            {"order_id": "O-5004", "amount": 10, "reason": "Again please."},
            "order_not_refundable",
            id="already-refunded",
        ),
        pytest.param(
            {"order_id": "O-5010", "amount": "64.01", "reason": "Too much."},
            "amount_exceeds_refundable",
            id="over-remaining",
        ),
        pytest.param(
            {"order_id": "O-5001", "amount": 0, "reason": "Zero."},
            "invalid_input",
            id="zero",
        ),
        pytest.param(
            {"order_id": "O-5001", "amount": -5, "reason": "Negative."},
            "invalid_input",
            id="negative",
        ),
        pytest.param(
            {"order_id": "O-5001", "amount": "1.005", "reason": "Fractions."},
            "invalid_input",
            id="sub-cent",
        ),
        pytest.param(
            {"order_id": "O-5001", "amount": 5},
            "invalid_input",
            id="missing-reason",
        ),
    ],
)
def test_refund_is_refused(
    registry: ToolRegistry,
    ctx: ToolContext,
    repo: InMemoryRepository,
    args: dict[str, object],
    error: str,
) -> None:
    order_id = str(args["order_id"])
    before = refunded_total(repo, order_id)

    result = registry.run(ctx, "issue_refund", args)

    assert result.is_error
    assert result.content["error"] == error
    assert refunded_total(repo, order_id) == before  # nothing was written


# Go: the classic table:
#   tests := []struct{ name string; args map[string]any; wantErr ErrorCode }{ ... }
#   for _, tc := range tests { t.Run(tc.name, func(t *testing.T) { ... }) }
# Every refusal is also checked for "no side effect" - the important property of a
# money-moving tool.


class _BoomInput(ToolInput):
    pass


def _boom(_ctx: ToolContext, _args: _BoomInput) -> BaseModel:
    msg = "database exploded"
    raise RuntimeError(msg)


def test_handler_crash_becomes_internal_error(ctx: ToolContext) -> None:
    registry = ToolRegistry(
        [Tool(name="boom", description="Always fails.", input_model=_BoomInput, handler=_boom)]
    )

    result = registry.run(ctx, "boom", {})

    assert result.is_error
    assert result.content["error"] == "internal_error"
    assert "exploded" not in str(result.content["message"])


# Go: a handler that panics; Run's recover() turns it into an error result. The
# internal message is logged, not sent to the model (it could leak internals).
