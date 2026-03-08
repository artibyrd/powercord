import os
from typing import Annotated

from fastapi import Header, HTTPException, status


async def verify_api_key(authorization: Annotated[str | None, Header()] = None):
    """
    Verifies the API key from the Authorization header.

    Expected header format: Authorization: Bearer <API_KEY>

    Args:
        authorization (str): The Authorization header value.

    Raises:
        HTTPException: If the API key is missing or invalid.
    """
    api_key = os.getenv("API_RELOAD_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfigured: API_RELOAD_KEY not set",
        )

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
        )

    scheme, _, param = authorization.partition(" ")
    if scheme.lower() != "bearer" or param != api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )
