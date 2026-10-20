"""The only tool that moves money.

Week 1 checks only the order's own facts (exists, status, amount left). The gates that
need the session - verification, ownership and the 500 USD handoff limit - arrive in
SD Phase 5, enforced in code in the Go MCP server. Until then nothing calls this from
a model, so there is no exposure.
"""

from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, Field, WithJsonSchema

from supportdesk.domain import OrderStatus, Refund, RefundStatus
from supportdesk.repository import refunded_total
from supportdesk.tools.base import ErrorCode, Tool, ToolContext, ToolError, ToolInput

REFUNDABLE_STATUSES = frozenset({OrderStatus.DELIVERED, OrderStatus.RETURNED})
CENT = Decimal("0.01")


def to_cents(value: Decimal) -> Decimal:
    return value.quantize(CENT)


# Go: amount.Round(2) with shopspring/decimal. 12.5 -> 12.50, so stored and displayed
# amounts always have exactly two decimals.

Amount = Annotated[
    Decimal,
    Field(gt=0, max_digits=10, decimal_places=2),
    AfterValidator(to_cents),
    WithJsonSchema({"type": "number", "exclusiveMinimum": 0, "description": "Amount in USD."}),
]

# Go: type Amount = decimal.Decimal  (+ validation in Validate()).
# Annotated[T, ...] attaches metadata to a type: validation rules, a post-validation
# transform (AfterValidator runs to_cents after the type and range checks pass), and a
# JSON schema override. Without the override pydantic advertises Decimal as "number OR
# a string matching a regex", which is noise for the model. 12.345 is still rejected
# (decimal_places=2) rather than silently rounded - never round money without telling.


class IssueRefundInput(ToolInput):
    order_id: str = Field(pattern=r"^O-\d{4}$", description="The order to refund, e.g. O-5001.")
    amount: Amount
    reason: str = Field(
        min_length=3,
        max_length=500,
        description="Why the refund is issued, in one sentence, for the audit log.",
    )


def issue_refund(ctx: ToolContext, args: IssueRefundInput) -> Refund | ToolError:
    order = ctx.repo.get_order(args.order_id)
    if order is None:
        return ToolError(error=ErrorCode.ORDER_NOT_FOUND, message=f"No order {args.order_id}.")

    if order.status not in REFUNDABLE_STATUSES:
        return ToolError(
            error=ErrorCode.ORDER_NOT_REFUNDABLE,
            message=f"Order {order.id} is '{order.status}'. Only delivered or returned orders "
            "can be refunded; for placed or shipped orders tell the customer to wait for "
            "delivery, and refunded orders cannot be refunded again.",
        )

    remaining = order.total - refunded_total(ctx.repo, order.id)
    if args.amount > remaining:
        return ToolError(
            error=ErrorCode.AMOUNT_EXCEEDS_REFUNDABLE,
            message=f"Requested {args.amount} USD but only {remaining} USD of order "
            f"{order.id} is still refundable.",
        )

    refund = Refund(
        id=ctx.repo.next_refund_id(),
        order_id=order.id,
        amount=args.amount,
        reason=args.reason,
        status=RefundStatus.ISSUED,
        created_at=ctx.now(),
    )
    ctx.repo.add_refund(refund)
    return refund


# Go:
#   func IssueRefund(ctx ToolContext, in IssueRefundInput) (any, *ToolError) {
#       o, ok := ctx.Repo.GetOrder(in.OrderID)
#       if !ok { return nil, &ToolError{OrderNotFound, ...} }
#       if !refundable[o.Status] { return nil, &ToolError{OrderNotRefundable, ...} }
#       remaining := o.Total.Sub(RefundedTotal(ctx.Repo, o.ID))
#       if in.Amount.GreaterThan(remaining) { return nil, &ToolError{...} }
#       r := Refund{ID: ctx.Repo.NextRefundID(), ..., CreatedAt: ctx.Now()}
#       ctx.Repo.AddRefund(r)
#       return r, nil
#   }
#
# Same early-return style as Go. `x not in frozenset` is a set lookup (map[T]bool in Go).
# f-strings format Decimal exactly ("82.00"), no float rounding.

ISSUE_REFUND = Tool(
    name="issue_refund",
    description=(
        "Issue a refund to the customer's original payment method for a delivered or "
        "returned order. The amount must not exceed the order's refundable amount (see "
        "lookup_order). Check the relevant policy with search_policies first. Returns the "
        "refund record, or an error explaining why the refund was not issued."
    ),
    input_model=IssueRefundInput,
    handler=issue_refund,
)
