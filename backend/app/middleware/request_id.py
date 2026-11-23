
from contextvars import ContextVar
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send


# ------------------------------------------------------------
# Request ID context
# ------------------------------------------------------------

request_id_context: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)


# ------------------------------------------------------------
# Request ID middleware
# ------------------------------------------------------------

class RequestIDMiddleware:
    """
    Pure ASGI middleware that assigns a unique ID
    to every incoming HTTP request.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:

        # Only process HTTP requests.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid4())

        # Store ID in the current async context.
        context_token = request_id_context.set(request_id)

        # Preserve the request ID on the ASGI scope.
        # This remains available even if the ContextVar is reset
        # before an outer exception handler executes.
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:

            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))

                headers.append(
                    (
                        b"x-request-id",
                        request_id.encode("ascii"),
                    )
                )

                message["headers"] = headers

            await send(message)

        try:
            await self.app(
                scope,
                receive,
                send_with_request_id,
            )

        finally:
            # Reset context after request processing.
            request_id_context.reset(context_token)
