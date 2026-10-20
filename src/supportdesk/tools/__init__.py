"""SupportDesk tools: plain functions plus the definitions Claude sees."""

from supportdesk.tools.base import ErrorCode, Tool, ToolContext, ToolError, ToolResult
from supportdesk.tools.registry import ToolRegistry, default_registry

__all__ = [
    "ErrorCode",
    "Tool",
    "ToolContext",
    "ToolError",
    "ToolRegistry",
    "ToolResult",
    "default_registry",
]

# Go: a package's exported API. Python has no capitalisation rule, so a package
# re-exports its public names from __init__.py, and __all__ lists them explicitly.
# Callers write `from supportdesk.tools import default_registry` and don't need to know
# the module layout inside the package.
