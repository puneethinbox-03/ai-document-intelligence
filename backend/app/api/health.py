from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.services.vectorstore.chroma_client import get_chroma_client


router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    """
    Check whether the FastAPI application is running.

    Does not depend on external services.
    """

    return {
        "status": "healthy"
    }


@router.get("/health/ready")
def readiness_check():
    """
    Check whether the application can communicate with ChromaDB.
    """

    try:
        client = get_chroma_client()
        client.heartbeat()

    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "checks": {
                    "chromadb": "unavailable"
                }
            },
        )

    return {
        "status": "ready",
        "checks": {
            "chromadb": "healthy"
        }
    }
