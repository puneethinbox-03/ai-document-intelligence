import logging

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings


logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# Redis connection configuration
# ------------------------------------------------------------

REDIS_CONNECT_TIMEOUT_SECONDS = 5
REDIS_SOCKET_TIMEOUT_SECONDS = 5
REDIS_HEALTH_CHECK_INTERVAL_SECONDS = 30


class RedisUnavailableError(RuntimeError):
    """
    Raised when Redis cannot be reached.

    Never include connection credentials or the Redis URL
    in this exception.
    """


# ------------------------------------------------------------
# Redis client factory
# ------------------------------------------------------------

def create_redis_client() -> Redis:
    """
    Create a synchronous Redis client using centralized settings.

    Credentials are retrieved from SecretStr and are never
    logged or included in application error messages.
    """

    return Redis.from_url(
        settings.redis_url.get_secret_value(),
        socket_connect_timeout=REDIS_CONNECT_TIMEOUT_SECONDS,
        socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
        health_check_interval=REDIS_HEALTH_CHECK_INTERVAL_SECONDS,
        decode_responses=False,
    )


# ------------------------------------------------------------
# Redis connectivity verification
# ------------------------------------------------------------

def verify_redis_connection(client: Redis) -> None:
    """
    Verify Redis connectivity using PING.

    Raises a safe application-level error when Redis is
    unavailable. Internal connection details are not exposed.
    """

    try:
        client.ping()

    except RedisError:
        logger.error(
            "Redis connection verification failed",
            extra={
                "event": "redis_connection_failed",
            },
        )

        raise RedisUnavailableError(
            "Background processing service is unavailable"
        ) from None
