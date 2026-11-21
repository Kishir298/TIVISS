"""Protocol identity constants.

Kept in its own module so :mod:`framing` and :mod:`pdp` can import them
without touching ``__init__`` (which imports those modules).
"""

from __future__ import annotations

PROTOCOL_NAME = "tiviss-security-protocol"
PROTOCOL_VERSION = 1

__all__ = ["PROTOCOL_NAME", "PROTOCOL_VERSION"]
