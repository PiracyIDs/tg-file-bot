"""
Redis connection manager for FSM state storage.
"""
import logging
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.redis import RedisStorage
import redis.asyncio as redis
from bot.config import settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None
_fsm_storage: BaseStorage | None = None


async def connect_to_redis() -> BaseStorage:
    """
    Connect to Redis and return a RedisStorage instance.
    Falls back to MemoryStorage if Redis is not available.
    """
    global _redis_client, _fsm_storage

    from aiogram.fsm.storage.memory import MemoryStorage

    if not settings.redis_uri:
        logger.warning("REDIS_URI not set, falling back to MemoryStorage")
        _fsm_storage = MemoryStorage()
        return _fsm_storage

    try:
        logger.info("Connecting to Redis at %s", settings.redis_uri)

        # Create Redis connection
        connection_kwargs = {
            "decode_responses": True,
            "socket_timeout": 5,
            "socket_connect_timeout": 5,
        }

        if settings.redis_password:
            connection_kwargs["password"] = settings.redis_password

        _redis_client = redis.from_url(
            settings.redis_uri,
            **connection_kwargs
        )

        # Test connection
        await _redis_client.ping()

        # Create FSM storage
        _fsm_storage = RedisStorage(redis=_redis_client)

        logger.info("Redis connected successfully for FSM storage")
        return _fsm_storage

    except Exception as exc:
        logger.error("Failed to connect to Redis: %s", exc)
        logger.warning("Falling back to MemoryStorage for FSM")
        _fsm_storage = MemoryStorage()
        return _fsm_storage


async def close_redis() -> None:
    """Close Redis connection."""
    global _redis_client

    if _redis_client:
        try:
            await _redis_client.close()
            logger.info("Redis connection closed.")
        except Exception as exc:
            logger.warning("Error closing Redis connection: %s", exc)


def get_fsm_storage() -> BaseStorage:
    """
    Get the current FSM storage instance.
    Raises RuntimeError if not initialized.
    """
    if _fsm_storage is None:
        raise RuntimeError("FSM storage not initialized. Call connect_to_redis() first.")
    return _fsm_storage
