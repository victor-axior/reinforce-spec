"""FastAPI dependencies (Depends callables).

Centralises dependency injection so routes stay thin and testable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request

    from reinforce_spec.client import ReinforceSpec


def get_client(request: Request) -> ReinforceSpec:
    """Extract the ``ReinforceSpec`` client from application state.

    This is injected via ``Depends(get_client)`` in route handlers.
    """
    client: ReinforceSpec = request.app.state.client
    return client
