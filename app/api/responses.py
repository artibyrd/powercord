from typing import Any, Generic, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel

T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    """
    Standard generic response model.

    Attributes:
        data (T): The response payload.
        message (str): A message describing the result.
        status (str): The status of the response (e.g., "success", "error").
    """

    data: T | None = None
    message: str = "Success"
    status: str = "success"


class ErrorResponse(BaseModel):
    """
    Standard error response model.

    Attributes:
        message (str): A message describing the error.
        status (str): The status of the response (always "error").
        details (Any): Optional additional error details.
    """

    message: str
    status: str = "error"
    details: Any | None = None


def success_response(data: Any = None, message: str = "Success", status_code: int = 200) -> JSONResponse:
    """
    Returns a standard success JSONResponse.

    Args:
        data (Any): The response payload.
        message (str): A success message.
        status_code (int): HTTP status code.

    Returns:
        JSONResponse: The formatted response.
    """
    content = StandardResponse(data=data, message=message, status="success").model_dump()
    return JSONResponse(status_code=status_code, content=content)


def error_response(message: str, details: Any = None, status_code: int = 400) -> JSONResponse:
    """
    Returns a standard error JSONResponse.

    Args:
        message (str): An error message.
        details (Any): Optional error details.
        status_code (int): HTTP status code.

    Returns:
        JSONResponse: The formatted error response.
    """
    content = ErrorResponse(message=message, details=details).model_dump()
    return JSONResponse(status_code=status_code, content=content)
