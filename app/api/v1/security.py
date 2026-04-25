"""Auth + RBAC helpers used across API namespaces."""
from __future__ import annotations

from functools import wraps
from typing import Iterable

from flask import abort, g
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.extensions import db
from app.models.user import User, UserRole


def current_user() -> User | None:
    """Resolve the authenticated user from the JWT identity."""
    identity = get_jwt_identity()
    if not identity:
        return None
    user = db.session.get(User, identity)
    g.current_user = user
    return user


def login_required(fn):
    """Wrap an endpoint with ``@jwt_required()`` AND fetch the user.

    Subsequent code can access ``g.current_user`` and ``g.tenant_id``
    without re-querying.
    """

    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or not user.is_active:
            abort(401, description="Inactive or unknown user")
        g.current_user = user
        g.tenant_id = user.tenant_id
        return fn(*args, **kwargs)

    return wrapper


def role_required(*allowed: UserRole | str):
    """Restrict an endpoint to a list of roles.

    Used in addition to (not instead of) ``login_required``.
    """
    allowed_set = {r.value if isinstance(r, UserRole) else r for r in allowed}

    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            user: User = g.current_user
            if user.role.value not in allowed_set and user.role != UserRole.ADMIN:
                abort(403, description=f"Role '{user.role.value}' not permitted")
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def assert_tenant(resource_tenant_id: str) -> None:
    """Defensive check — raises 403 if a resource belongs to another tenant.

    Repository queries should already be tenant-scoped, but this helper
    catches accidental cross-tenant access in handler code.
    """
    if g.get("tenant_id") and resource_tenant_id != g.tenant_id:
        abort(403, description="Cross-tenant access denied")


# ---------------------------------------------------------------------------
# Module-level permissions
# ---------------------------------------------------------------------------

def has_module(user, module_code: str) -> bool:
    """Return True iff the user can access the named module.

    OWNER + ADMIN roles implicitly have every module. All other roles
    must have an explicit grant in user_module_permissions.
    """
    if user is None:
        return False
    if user.role in (UserRole.OWNER, UserRole.ADMIN):
        return True
    from app.models.permission import UserModulePermission
    return (UserModulePermission.query
            .filter_by(user_id=user.id,
                       tenant_id=user.tenant_id,
                       module_code=module_code)
            .first() is not None)


def module_required(module_code: str):
    """Restrict an endpoint to users who hold the named module grant.

    Used in addition to (not instead of) ``login_required``.
    Returns 403 if the caller lacks the grant.
    """
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            user = g.current_user
            if not has_module(user, module_code):
                abort(403, description=f"Missing module grant: {module_code}")
            return fn(*args, **kwargs)
        return wrapper
    return decorator

