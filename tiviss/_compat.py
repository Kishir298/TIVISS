"""Python version compatibility shims.

TIVISS supports Python >= 3.10.  Constructs that are only available on newer
interpreters are re-exported here so the rest of the codebase can import a
single, stable location.
"""

from __future__ import annotations

from enum import Enum

try:  # Python 3.11+
    from enum import StrEnum
except ImportError:  # pragma: no cover - exercised on Python 3.10 CI legs

    class StrEnum(str, Enum):
        """PEP 681 ``enum.StrEnum`` backport for Python 3.10.

        Behaves like the 3.11+ builtin: members are ``str`` instances whose
        ``str()``/``format()`` render the *value* (not ``ClassName.MEMBER``).
        """

        def __str__(self) -> str:  # noqa: D102
            return str(self.value)

        def __format__(self, format_spec: str) -> str:  # noqa: D102
            return str.__format__(str(self.value), format_spec)


try:  # Python 3.11+
    from datetime import UTC
except ImportError:  # pragma: no cover - exercised on Python 3.10 CI legs
    from datetime import timezone

    UTC = timezone.utc  # type: ignore[assignment]


__all__ = ["StrEnum", "UTC"]
