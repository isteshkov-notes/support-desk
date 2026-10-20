from functools import cache
from typing import Annotated

from anthropic.types import ToolParam
from fastapi import Depends, FastAPI

from supportdesk.tools import ToolRegistry, default_registry

app = FastAPI(title="SupportDesk")
# Go:
#   var app = http.NewServeMux()
# A module-level variable is created once, the first time the module is imported
# (like a package-level var initialised before main runs).


@cache
def get_registry() -> ToolRegistry:
    return default_registry()


# Go:
#   var registryOnce = sync.OnceValue(func() *ToolRegistry { return DefaultRegistry() })
# A cached provider function. FastAPI calls it through Depends (below); tests swap it
# with app.dependency_overrides[get_registry] = lambda: fake_registry.


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Go:
#   func health(w http.ResponseWriter, r *http.Request) {
#       w.Header().Set("Content-Type", "application/json")
#       json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
#   }
#   func init() { app.HandleFunc("GET /health", health) }
#
# The @app.get decorator is the HandleFunc call: it registers the function when the
# module is imported. You return a plain dict; FastAPI does the JSON encoding, the
# Content-Type header and the 200 status (the return type also feeds the OpenAPI docs
# at /docs). `async def` runs on the event loop; it must never block (no time.sleep,
# no sync HTTP) - in Go a blocking handler just parks its goroutine, here it would
# stall every request.


@app.get("/tools")
async def list_tools(
    registry: Annotated[ToolRegistry, Depends(get_registry)],
) -> list[ToolParam]:
    return registry.definitions()


# Go (manual dependency injection via a closure):
#   func listTools(reg *ToolRegistry) http.HandlerFunc {
#       return func(w http.ResponseWriter, r *http.Request) {
#           json.NewEncoder(w).Encode(reg.Definitions())
#       }
#   }
#   app.HandleFunc("GET /tools", listTools(registry))
#
# Depends(get_registry) tells FastAPI: "call get_registry() and pass the result in as
# `registry`". It's DI resolved per request instead of wired once in main().
# Annotated[Type, Depends(...)] keeps the real type visible to pyright.
# This endpoint shows exactly what Claude will see as tool definitions - handy for
# debugging descriptions and schemas: curl localhost:8000/tools | jq
