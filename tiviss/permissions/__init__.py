"""Permission model and default-deny policies."""

from .confirmation import (
    DANGEROUS_PERMISSION_PREFIXES,
    broker_approver,
    broker_configured,
    is_dangerous,
)
from .permissions import (
    Permission,
    PermissionContext,
    PermissionDeniedError,
    PermissionValidationError,
)
from .policy import DefaultDenyPolicy, PermissionPolicy

__all__ = [
    "Permission",
    "PermissionContext",
    "PermissionDeniedError",
    "PermissionValidationError",
    "DefaultDenyPolicy",
    "PermissionPolicy",
    "DANGEROUS_PERMISSION_PREFIXES",
    "broker_approver",
    "broker_configured",
    "is_dangerous",
]
