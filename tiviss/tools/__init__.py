"""Tool abstraction: interface, results, registry, and safe mock tools."""

from .interface import Tool, ToolError, ToolResult
from .registry import ToolRegistry

__all__ = ["Tool", "ToolError", "ToolResult", "ToolRegistry"]