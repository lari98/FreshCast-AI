"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from freshcast_api.db import session_scope


def get_session(request: Request) -> Iterator[Session]:
    """Provide a request-scoped database session."""
    yield from session_scope(request.app.state.session_factory)


SessionDep = Annotated[Session, Depends(get_session)]
