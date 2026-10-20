# SupportDesk

A multi-agent customer-support assistant for **ShopCo**, a fictional online shop, built on
Claude. It's the capstone project of a 16-week AI Engineer / FDE prep plan; the full spec,
phase by phase, is in [`docs/SPEC.md`](docs/SPEC.md), and the target architecture (C4 diagrams)
is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

**Status:** week 1 done: SD Phase 0 (skeleton, CI) and SD Phase 1 (fake data and four
tested tools). No model calls yet; the agent loop arrives in week 2.

## Quick start

```bash
uv sync                      # create .venv with the pinned Python (3.13) and all deps
cp .env.example .env         # add ANTHROPIC_API_KEY (needed from week 2)
uv run supportdesk           # http://127.0.0.1:8000/health and /tools, docs at /docs
```

Or with Docker: `docker compose --profile full up --build` (also starts Postgres with
pgvector and Redis, used from week 4).

## Checks (the same ones CI runs)

```bash
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
```

## Layout

```
src/supportdesk/
  __main__.py        entry point: `uv run supportdesk` / `python -m supportdesk`
  main.py            FastAPI app: GET /health, GET /tools
  config.py          Settings from env / .env (pydantic-settings)
  domain.py          Customer, Order, Refund, PolicyDoc ... (pydantic, frozen)
  repository.py      Repository protocol + in-memory JSON implementation
  data/*.json        fixtures: 6 customers, 15 orders, 2 refunds, 6 policy docs
  tools/
    base.py          Tool wrapper, ToolContext, ToolResult, ToolError
    account.py       get_customer, lookup_order
    policies.py      search_policies (naive keyword search, replaced in week 4)
    refunds.py       issue_refund
    registry.py      ToolRegistry: definitions for Claude + dispatch by name
tests/               pytest, no network calls
```

## Tools

| Tool | What it does | Errors (returned as data) |
| --- | --- | --- |
| `get_customer` | Profile, tier, loyalty points | `customer_not_found`, `invalid_input` |
| `lookup_order` | Order, items, status, dates, notes, refunded and refundable amounts | `order_not_found`, `invalid_input` |
| `search_policies` | Top-k policy sections with citations (`POL-RETURNS §1`) | `invalid_input`; no match is an empty list |
| `issue_refund` | Records a refund for a delivered or returned order | `order_not_found`, `order_not_refundable`, `amount_exceeds_refundable`, `invalid_input` |

Each tool is a plain function plus a definition (`name`, `description`, `input_schema`)
whose JSON schema is generated from a pydantic model, so what Claude sees and what the
code validates can't drift apart. `curl localhost:8000/tools` shows exactly what the model
will get.

Verification, ownership and the 500 USD handoff limit are **not** enforced yet. They are
SD Phase 5 gates, enforced in code in the Go MCP server.

## Fixture edge cases (used by later phases)

| Order | Case |
| --- | --- |
| O-5003 | Shipped, not delivered: "Where is my order?" (week 2 smoke prompt) |
| O-5007 | Tablet, slow delivery: the 3-concern sample message (week 5) |
| O-5009 | Delivered 31 days before 2026-10-20, one day past the return window |
| O-5010 | Partially refunded already (18.00 of 82.00) |
| O-5011 | 900 USD laptop, which must become a handoff (week 6) |
| O-5013 | `notes` contains a prompt injection (trap #6) |
