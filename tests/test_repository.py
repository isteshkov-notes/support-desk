from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from supportdesk.domain import Customer, OrderStatus, Tier
from supportdesk.repository import (
    InMemoryRepository,
    load_customers,
    load_orders,
    load_policies,
    load_refunds,
    refunded_total,
)
from tests.conftest import FIXED_NOW


def test_fixture_sizes_match_the_spec() -> None:
    assert len(load_customers()) == 6
    assert len(load_orders()) == 15
    assert len(load_refunds()) == 2
    assert len(load_policies()) == 6


# Go: same-package tests may read unexported fields; here pyright strict forbids touching
# repo._orders from outside the class, so tests use the public loaders instead.


def test_order_totals_match_their_items() -> None:
    for order in load_orders():
        assert order.total == sum(i.unit_price * i.qty for i in order.items), order.id


# Go:
#   for _, o := range orders {
#       if o.Total != sumItems(o) { t.Errorf("%s: total mismatch", o.ID) }
#   }
# The text after the comma is the assert's failure message.


def test_references_point_to_existing_records(repo: InMemoryRepository) -> None:
    for order in load_orders():
        assert repo.get_customer(order.customer_id) is not None, order.id
    for refund in load_refunds():
        assert repo.get_order(refund.order_id) is not None, refund.id


def test_refunded_orders_are_fully_refunded(repo: InMemoryRepository) -> None:
    for order in load_orders():
        if order.status is OrderStatus.REFUNDED:
            assert refunded_total(repo, order.id) == order.total, order.id


# `is` on enum members: each member is a singleton, so identity comparison is exact.


def test_spec_edge_cases_are_present() -> None:
    customers = load_customers()
    orders = load_orders()

    assert any(c.tier is Tier.GOLD for c in customers)
    assert any(o.total == Decimal("900.00") for o in orders)
    assert any(o.notes and "SYSTEM:" in o.notes for o in orders)
    assert any(o.delivered_at and FIXED_NOW - o.delivered_at == timedelta(days=31) for o in orders)


# Go:
#   if !slices.ContainsFunc(customers, func(c Customer) bool { return c.Tier == TierGold }) {
#       t.Error("no gold customer")
#   }
# any(generator) == slices.ContainsFunc. Datetime minus datetime is a timedelta
# (time.Duration). `a and b` returns a if it's falsy - here None-safe access.


def test_lookups_return_none_when_missing(repo: InMemoryRepository) -> None:
    assert repo.get_customer("C-0000") is None
    assert repo.get_order("O-0000") is None
    assert repo.refunds_for_order("O-0000") == []


def test_next_refund_id_follows_the_highest_existing(repo: InMemoryRepository) -> None:
    assert repo.next_refund_id() == "R-9003"


def test_unknown_fields_in_data_are_rejected() -> None:
    with pytest.raises(ValidationError, match="loyalty_pionts"):
        Customer.model_validate(
            {
                "id": "C-1999",
                "name": "Typo",
                "email": "t@example.com",
                "tier": "standard",
                "loyalty_points": 1,
                "loyalty_pionts": 1,
                "created_at": "2026-01-01T00:00:00Z",
            }
        )


# Go: json.NewDecoder(r).DisallowUnknownFields() returning an error. extra="forbid" on
# the models catches typos in the fixture files.


def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        Customer.model_validate(
            {
                "id": "C-1999",
                "name": "No TZ",
                "email": "t@example.com",
                "tier": "standard",
                "loyalty_points": 0,
                "created_at": "2026-01-01T00:00:00",
            }
        )


# Go has no naive time.Time (it always carries a Location); in Python it's a common bug,
# so AwareDatetime enforces it.
