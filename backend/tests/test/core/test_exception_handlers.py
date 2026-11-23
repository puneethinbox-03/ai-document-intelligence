from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import general_exception_handler
from app.middleware.request_id import RequestIDMiddleware


exception_test_application = FastAPI()

exception_test_application.add_exception_handler(
    Exception,
    general_exception_handler,
)

exception_test_application.add_middleware(RequestIDMiddleware)


@exception_test_application.get("/test/unhandled-error")
def raise_unhandled_error():
    raise RuntimeError("secret-internal-message")


def test_unhandled_exception_returns_request_id_and_safe_error():
    client = TestClient(
        exception_test_application,
        raise_server_exceptions=False,
    )

    response = client.get("/test/unhandled-error")

    assert response.status_code == 500

    data = response.json()
    error = data["error"]

    assert error["code"] == "INTERNAL_SERVER_ERROR"
    assert (
        error["message"]
        == "An unexpected internal server error occurred"
    )

    body_request_id = error["request_id"]
    header_request_id = response.headers.get("x-request-id")

    assert body_request_id is not None
    assert header_request_id is not None
    assert body_request_id == header_request_id

    assert "secret-internal-message" not in response.text
