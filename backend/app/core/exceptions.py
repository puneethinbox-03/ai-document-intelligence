
import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.middleware.request_id import request_id_context


logger = logging.getLogger(__name__)


# ============================================================
# Request ID Helper
# ============================================================

def get_request_id(request: Request) -> str | None:
    """
    Retrieve the request ID from the request scope.

    Fall back to the ContextVar when necessary.
    """

    return (
        getattr(request.state, "request_id", None)
        or request_id_context.get()
    )


# ============================================================
# Application Exceptions
# ============================================================

class AppException(Exception):
    """
    Base class for application-specific exceptions.

    Attributes:
        message: Safe, user-facing error message.
        code: Stable machine-readable error identifier.
        status_code: HTTP status code associated with the error.
    """

    def __init__(
        self,
        message: str,
        code: str = "APPLICATION_ERROR",
        status_code: int = 400,
    ) -> None:
        super().__init__(message)

        self.message = message
        self.code = code
        self.status_code = status_code


class DocumentNotFoundError(AppException):
    """Raised when a requested document does not exist."""

    def __init__(
        self,
        message: str = "Document not found",
    ) -> None:
        super().__init__(
            message=message,
            code="DOCUMENT_NOT_FOUND",
            status_code=404,
        )


class DocumentProcessingError(AppException):
    """Raised when document processing fails."""

    def __init__(
        self,
        message: str = "Document processing failed",
    ) -> None:
        super().__init__(
            message=message,
            code="DOCUMENT_PROCESSING_ERROR",
            status_code=500,
        )


# ============================================================
# Standard Error Response Builder
# ============================================================

def build_error_response(
    code: str,
    message: str,
    request_id: str | None = None,
    details: Any = None,
) -> dict[str, Any]:
    """
    Build the standard API error response.

    Internal exception details must never be passed to this
    function for unexpected server errors.
    """

    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": request_id,
    }

    if details is not None:
        error["details"] = details

    return {
        "error": error,
    }


# ============================================================
# Application Exception Handler
# ============================================================

async def app_exception_handler(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    """
    Handle known application exceptions.
    """

    request_id = get_request_id(request)

    logger.warning(
        "Application exception occurred",
        extra={
            "event": "application_exception",
            "error_code": exc.code,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_response(
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        ),
    )


# ============================================================
# HTTP Exception Handler
# ============================================================

async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """
    Convert FastAPI/Starlette HTTP exceptions
    into the standard error response.
    """

    request_id = get_request_id(request)

    message = (
        exc.detail
        if isinstance(exc.detail, str)
        else "The request could not be completed"
    )

    error_code = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        413: "PAYLOAD_TOO_LARGE",
        415: "UNSUPPORTED_MEDIA_TYPE",
        422: "VALIDATION_ERROR",
        429: "TOO_MANY_REQUESTS",
    }.get(exc.status_code, "HTTP_ERROR")

    if exc.status_code >= 500:
        message = "An internal server error occurred"

    logger.warning(
        "HTTP exception occurred",
        extra={
            "event": "http_exception",
            "error_code": error_code,
            "status_code": exc.status_code,
        },
    )

    response = JSONResponse(
        status_code=exc.status_code,
        content=build_error_response(
            code=error_code,
            message=message,
            request_id=request_id,
        ),
    )

    if exc.headers:
        response.headers.update(exc.headers)

    return response


# ============================================================
# Request Validation Exception Handler
# ============================================================

async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Handle invalid request data.

    Validation locations and messages are returned as
    structured details. Submitted input values are excluded.
    """

    request_id = get_request_id(request)

    validation_details = [
        {
            "location": list(error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]

    logger.warning(
        "Request validation failed",
        extra={
            "event": "request_validation_error",
            "error_code": "VALIDATION_ERROR",
        },
    )

    return JSONResponse(
        status_code=422,
        content=build_error_response(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            request_id=request_id,
            details=validation_details,
        ),
    )


# ============================================================
# General Exception Handler
# ============================================================

async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Handle unexpected application errors.

    Never expose internal exception messages to clients.
    """

    request_id = get_request_id(request)

    logger.error(
        "Unexpected application error",
        extra={
            "event": "unhandled_exception",
            "error_code": "INTERNAL_SERVER_ERROR",
        },
        exc_info=(
            type(exc),
            exc,
            exc.__traceback__,
        ),
    )
    return JSONResponse(
        status_code=500,
        content=build_error_response(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal server error occurred",
            request_id=request_id,
        ),
        headers={
            "X-Request-ID": request_id,
        } if request_id else None,
    )
