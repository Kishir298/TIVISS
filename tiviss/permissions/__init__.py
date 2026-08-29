"""Permission model and default-deny policies."""

from .permissions import Permission, PermissionContext, PermissionDeniedError
from .policy import DefaultDenyPolicy, PermissionPolicy

__all__ = ["Permission", "PermissionContext", "PermissionDeniedError", "DefaultDenyPolicy", "PermissionPolicy"]