
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.documents import router as documents_router
from app.api.rag import router as rag_router
from app.api.health import router as health_router

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)

from app.middleware.request_id import RequestIDMiddleware


# Initialize centralized structured logging.
configure_logging()


app = FastAPI(
    title=settings.app_name,
    description="AI-powered document intelligence and RAG API",
    version=settings.app_version,
    debug=settings.debug,
)


# ------------------------------------------------------------
# Exception Handlers
# ------------------------------------------------------------

app.add_exception_handler(
    AppException,
    app_exception_handler,
)

app.add_exception_handler(
    StarletteHTTPException,
    http_exception_handler,
)

app.add_exception_handler(
    RequestValidationError,
    validation_exception_handler,
)

app.add_exception_handler(
    Exception,
    general_exception_handler,
)


# ------------------------------------------------------------
# Request ID Middleware
# ------------------------------------------------------------

app.add_middleware(RequestIDMiddleware)


# ------------------------------------------------------------
# CORS Configuration
# ------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["X-Request-ID"],
)


# ------------------------------------------------------------
# API Routers
# ------------------------------------------------------------

app.include_router(documents_router)
app.include_router(rag_router)
app.include_router(health_router)


# ------------------------------------------------------------
# Root Endpoint
# ------------------------------------------------------------

@app.get("/")
def root():
    return {
        "message": f"{settings.app_name} API is running!"
    }
