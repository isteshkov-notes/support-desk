"""Domain entities shared by the repository, the tools and (later) the agents."""

from decimal import Decimal
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

# Go:
#   type Tier string
#   const ( TierStandard Tier = "standard"; TierGold Tier = "gold" )
#
# StrEnum members ARE strings: Tier.GOLD == "gold" is True and they serialise to JSON
# as plain strings. Pydantic rejects any value that isn't a member, like a
# hand-written UnmarshalJSON that validates the constant.


class Tier(StrEnum):
    STANDARD = "standard"
    GOLD = "gold"


class OrderStatus(StrEnum):
    PLACED = "placed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    RETURNED = "returned"
    REFUNDED = "refunded"


class RefundStatus(StrEnum):
    ISSUED = "issued"


class Entity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# Go: there's no base-struct config in Go; this is like every struct below having
#   json tags + DisallowUnknownFields() on decode + no exported setters.
# frozen=True makes instances immutable (assignment raises) and hashable.
# extra="forbid" turns a typo in the JSON fixtures ("loyalty_pionts") into an error
# instead of a silently ignored field.


class Customer(Entity):
    id: str = Field(pattern=r"^C-\d{4}$")
    name: str
    email: str
    tier: Tier
    loyalty_points: int = Field(ge=0)
    created_at: AwareDatetime


# Go:
#   type Customer struct {
#       ID            string    `json:"id"`
#       Name          string    `json:"name"`
#       Email         string    `json:"email"`
#       Tier          Tier      `json:"tier"`
#       LoyaltyPoints int       `json:"loyalty_points"`
#       CreatedAt     time.Time `json:"created_at"`
#   }
#   func (c Customer) Validate() error { /* regex on ID, points >= 0, ... */ }
#
# Pydantic merges the struct, the json tags and Validate() into one declaration:
# validation runs automatically on construction, so an invalid Customer can't exist.
# AwareDatetime rejects timestamps without a timezone (spec: always UTC-aware).


class OrderItem(Entity):
    sku: str
    name: str
    qty: int = Field(ge=1)
    unit_price: Decimal = Field(ge=0, decimal_places=2)


class Order(Entity):
    id: str = Field(pattern=r"^O-\d{4}$")
    customer_id: str
    items: tuple[OrderItem, ...] = Field(min_length=1)
    total: Decimal = Field(ge=0, decimal_places=2)
    currency: str = "USD"
    status: OrderStatus
    placed_at: AwareDatetime
    delivered_at: AwareDatetime | None = None
    notes: str | None = None


# Go:
#   type Order struct {
#       ...
#       Items       []OrderItem     `json:"items"`
#       Total       decimal.Decimal `json:"total"`        // shopspring/decimal
#       DeliveredAt *time.Time      `json:"delivered_at,omitempty"`
#       Notes       *string         `json:"notes,omitempty"`
#   }
#
# `X | None = None` is Go's pointer-for-optional. tuple[...] instead of list keeps the
# frozen model truly immutable. Decimal is in the stdlib (Go needs a library): money
# is never float, because 0.1 + 0.2 != 0.3 in binary floating point.


class Refund(Entity):
    id: str = Field(pattern=r"^R-\d{4}$")
    order_id: str
    amount: Decimal = Field(gt=0, decimal_places=2)
    reason: str
    status: RefundStatus
    created_at: AwareDatetime


class PolicySection(Entity):
    id: str
    heading: str
    text: str


class PolicyDoc(Entity):
    id: str = Field(pattern=r"^POL-[A-Z-]+$")
    title: str
    sections: tuple[PolicySection, ...] = Field(min_length=1)


# Citations point at a section: "POL-RETURNS §2" = PolicyDoc.id + PolicySection.id.
