"""Memory abstraction: interface, models, and a deterministic local backend."""

from .interface import MemoryBackend, MemoryRecord, MemorySearchResult
from .local import LocalMemory

__all__ = ["MemoryBackend", "MemoryRecord", "MemorySearchResult", "LocalMemory"]