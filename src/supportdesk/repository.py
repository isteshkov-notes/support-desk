"""Data access. Tools depend on the `Repository` protocol, never on where data lives.

Week 1: JSON fixtures shipped inside the package. Week 4: a Postgres implementation of
the same protocol replaces it without touching the tools.
"""

from collections.abc import Sequence
from decimal import Decimal
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Protocol

from pydantic import TypeAdapter

from supportdesk.domain import Customer, Order, PolicyDoc, Refund


class Repository(Protocol):
    def get_customer(self, customer_id: str) -> Customer | None: ...
    def get_order(self, order_id: str) -> Order | None: ...
    def list_policies(self) -> Sequence[PolicyDoc]: ...
    def refunds_for_order(self, order_id: str) -> Sequence[Refund]: ...
    def add_refund(self, refund: Refund) -> None: ...
    def next_refund_id(self) -> str: ...


# Go:
#   type Repository interface {
#       GetCustomer(id string) (*Customer, bool)
#       GetOrder(id string) (*Order, bool)
#       ListPolicies() []PolicyDoc
#       RefundsForOrder(orderID string) []Refund
#       AddRefund(r Refund)
#       NextRefundID() string
#   }
#
# Protocol = Go interface: satisfied *structurally*. InMemoryRepository below never
# says "implements Repository"; pyright checks the method shapes wherever one is passed
# as a Repository. (The alternative, abc.ABC, is nominal: you must inherit from it.)
# `X | None` replaces Go's (value, ok) pair. `...` is the body of a declaration-only
# method.


def refunded_total(repo: Repository, order_id: str) -> Decimal:
    return sum((r.amount for r in repo.refunds_for_order(order_id)), Decimal(0))


# Go:
#   func RefundedTotal(repo Repository, orderID string) decimal.Decimal {
#       total := decimal.Zero
#       for _, r := range repo.RefundsForOrder(orderID) { total = total.Add(r.Amount) }
#       return total
#   }
# A plain function that takes the interface - works with any Repository implementation.
# sum() needs the Decimal(0) start value, otherwise it starts from int 0.


DEFAULT_DATA = files("supportdesk") / "data"
# Go:
#   //go:embed data/*.json
#   var defaultData embed.FS
# importlib.resources finds files that ship *inside the package*, so this works from
# the source tree, from an installed wheel and in Docker alike. A path built from the
# current working directory would only work when you run from the repo root.


def load_customers(data: Traversable = DEFAULT_DATA) -> list[Customer]:
    return TypeAdapter(list[Customer]).validate_json((data / "customers.json").read_bytes())


def load_orders(data: Traversable = DEFAULT_DATA) -> list[Order]:
    return TypeAdapter(list[Order]).validate_json((data / "orders.json").read_bytes())


def load_refunds(data: Traversable = DEFAULT_DATA) -> list[Refund]:
    return TypeAdapter(list[Refund]).validate_json((data / "refunds.json").read_bytes())


def load_policies(data: Traversable = DEFAULT_DATA) -> list[PolicyDoc]:
    return TypeAdapter(list[PolicyDoc]).validate_json((data / "policies.json").read_bytes())


# Go:
#   func LoadCustomers(fsys fs.FS) ([]Customer, error) {
#       b, err := fs.ReadFile(fsys, "customers.json")
#       if err != nil { return nil, err }
#       var cs []Customer
#       if err := json.Unmarshal(b, &cs); err != nil { return nil, err }
#       for _, c := range cs { if err := c.Validate(); err != nil { return nil, err } }
#       return cs, nil
#   }
#
# TypeAdapter validates types that aren't a BaseModel themselves (here list[Customer]).
# validate_json parses + validates in one pass (in Rust, fast). Errors are raised
# (pydantic.ValidationError), not returned: bad fixtures should crash at startup.


class InMemoryRepository:
    def __init__(
        self,
        customers: Sequence[Customer],
        orders: Sequence[Order],
        refunds: Sequence[Refund],
        policies: Sequence[PolicyDoc],
    ) -> None:
        self._customers = {c.id: c for c in customers}
        self._orders = {o.id: o for o in orders}
        self._refunds = list(refunds)
        self._policies = tuple(policies)

    # Go:
    #   type InMemoryRepository struct {
    #       customers map[string]Customer
    #       ...
    #   }
    #   func NewInMemoryRepository(cs []Customer, ...) *InMemoryRepository {
    #       m := make(map[string]Customer, len(cs))
    #       for _, c := range cs { m[c.ID] = c }
    #       ...
    #   }
    # __init__ is the constructor. `{c.id: c for c in customers}` is a dict
    # comprehension: the for-loop that builds the map, in one expression.
    # A leading underscore means "private by convention" (Python has no unexported
    # identifiers; ruff/pyright warn when other modules touch _names).

    @classmethod
    def from_data(cls, data: Traversable = DEFAULT_DATA) -> "InMemoryRepository":
        return cls(
            customers=load_customers(data),
            orders=load_orders(data),
            refunds=load_refunds(data),
            policies=load_policies(data),
        )

    # Go:
    #   func NewInMemoryRepositoryFromFS(fsys fs.FS) (*InMemoryRepository, error)
    # @classmethod receives the class (cls) instead of an instance: it's the idiomatic
    # "alternative constructor". Keyword arguments (customers=...) make the call
    # self-documenting, like a struct literal with field names.

    def get_customer(self, customer_id: str) -> Customer | None:
        return self._customers.get(customer_id)

    def get_order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    # Go:
    #   func (r *InMemoryRepository) GetOrder(id string) (Order, bool) {
    #       o, ok := r.orders[id]
    #       return o, ok
    #   }
    # dict.get returns None for a missing key (dict[key] would raise KeyError).

    def list_policies(self) -> Sequence[PolicyDoc]:
        return self._policies

    def refunds_for_order(self, order_id: str) -> Sequence[Refund]:
        return [r for r in self._refunds if r.order_id == order_id]

    # Go:
    #   var out []Refund
    #   for _, r := range r.refunds { if r.OrderID == orderID { out = append(out, r) } }
    #   return out
    # A list comprehension = filter loop in one expression.

    def add_refund(self, refund: Refund) -> None:
        self._refunds.append(refund)

    def next_refund_id(self) -> str:
        highest = max((int(r.id.removeprefix("R-")) for r in self._refunds), default=9000)
        return f"R-{highest + 1}"

    # Go:
    #   highest := 9000
    #   for _, r := range r.refunds {
    #       n, _ := strconv.Atoi(strings.TrimPrefix(r.ID, "R-"))
    #       highest = max(highest, n)
    #   }
    #   return fmt.Sprintf("R-%d", highest+1)
    # The (... for r in ...) without brackets is a generator expression: lazy, no
    # intermediate list. Not safe for concurrent writers - fine for in-memory dev data;
    # Postgres will use a sequence.
