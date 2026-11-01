"""Authentication and role-based access control (RBAC).

Production identity comes from Amazon Cognito JWTs (phase 7). Until then a
header-based principal is accepted ONLY when FRESHCAST_ENV=local, so the
insecure path can never be active in a deployed environment.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from freshcast_api.config import Settings


class Role(StrEnum):
    """Least-privilege roles."""

    VIEWER = "viewer"
    STORE_MANAGER = "store_manager"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated caller."""

    user: str
    role: Role


def get_principal(
    request: Request,
    x_dev_user: Annotated[str | None, Header()] = None,
    x_dev_role: Annotated[str | None, Header()] = None,
) -> Principal:
    """Resolve the caller or reject the request."""
    settings: Settings = request.app.state.settings
    if settings.env != "local":
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "JWT validation (Cognito) is not implemented yet",
        )
    if not x_dev_user or not x_dev_role:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing credentials")
    try:
        return Principal(user=x_dev_user, role=Role(x_dev_role))
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown role") from None


def require_role(*allowed: Role) -> Callable[[Principal], Principal]:
    """Build a dependency that admits only the listed roles."""

    def checker(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return principal

    return checker
