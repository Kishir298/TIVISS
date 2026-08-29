"""Tool abstraction: interface, registry, results, and safe mock tools."""

from .interface import Tool, ToolError, ToolResult, ToolStatus
from .mock_tools import EchoTool, FailingTool, SumTool
from .registry import ToolRegistry, UnknownToolError

__all__ = [
    "Tool",
    "ToolError",
    "ToolResult",
    "ToolStatus",
    "ToolRegistry",
    "UnknownToolError",
    "EchoTool",
    "SumTool",
    "FailingTool",
]
