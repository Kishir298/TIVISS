"""Memory abstraction: interface, models, and a deterministic local backend."""

from .interface import MemoryBackend, MemoryKeyError, MemoryRecord, MemorySearchResult
from .local import LocalMemory

__all__ = [
    "MemoryBackend",
    "MemoryKeyError",
    "MemoryRecord",
    "MemorySearchResult",
    "LocalMemory",
]
