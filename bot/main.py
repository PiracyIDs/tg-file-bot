"""
Bot entry point — Enhanced Edition.
Wires together aiogram, MongoDB, Redis FSM storage, background tasks,
middleware, and all routers with proper error tracking and graceful shutdown.
"""
import asyncio
import logging
import signal
import sys
from contextlib import suppress

import sentry_sdk
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from bot.config import settings
from bot.database.connection import connect_to_mongo, close_mongo
from bot.database.redis_connection import connect_to_redis, close_redis
from bot.handlers import admin, common, download, upload
from bot.middlewares.auth import AllowlistMiddleware
from bot.tasks.expiry_task import expiry_warning_task

# Global shutdown event
_shutdown_event = asyncio.Event()


def setup_logging() -> None:
    """Configure structured logging for the application."""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s — %(message)s"

    # Default logging config
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    # Configure logging for third-party libraries
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)


async def on_startup(bot: Bot) -> None:
    """Initialize connections and verify storage channel."""
    logger = logging.getLogger(__name__)

    logger.info("Initializing connections...")

    # Connect to MongoDB
    await connect_to_mongo()

    # Connect to Redis for FSM storage
    await connect_to_redis()

    # Verify storage channel access
    try:
        chat = await bot.get_chat(settings.storage_channel_id)
        logger.info("Storage channel OK: '%s' (id=%s)", chat.title, chat.id)
    except Exception as exc:
        logger.critical(
            "Cannot access storage channel %s: %s", settings.storage_channel_id, exc
        )
        raise SystemExit(1)

    logger.info("Startup complete. Bot is ready.")


async def on_shutdown(bot: Bot) -> None:
    """Cleanup: close connections and flush pending tasks."""
    logger = logging.getLogger(__name__)

    logger.info("Graceful shutdown initiated...")

    # Close MongoDB connection
    await close_mongo()

    # Close Redis connection
    await close_redis()

    # Close bot session
    await bot.session.close()

    logger.info("Shutdown complete.")


def setup_sentry() -> None:
    """Initialize Sentry for error tracking and monitoring."""
    if not settings.sentry_dsn:
        logging.getLogger(__name__).info("Sentry DSN not configured, skipping error tracking")
        return

    try:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.sentry_environment,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            # Filter out specific exceptions if needed
            ignore_errors=[
                asyncio.CancelledError,
                SystemExit,
                KeyboardInterrupt,
            ],
            # Set up integrations
            integrations=[
                # AIogram integration can be added when available
            ],
            # Performance monitoring
            enable_tracing=settings.sentry_traces_sample_rate > 0,
        )
        logging.getLogger(__name__).info(
            "Sentry initialized (environment: %s, traces: %.1f%%)",
            settings.sentry_environment,
            settings.sentry_traces_sample_rate * 100,
        )
    except Exception as exc:
        logging.getLogger(__name__).error("Failed to initialize Sentry: %s", exc)


def setup_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    """Setup signal handlers for graceful shutdown."""

    def signal_handler(signum: int) -> None:
        """Handle shutdown signals."""
        logging.getLogger(__name__).info(
            "Received signal %s, initiating graceful shutdown...",
            signal.Signals(signum).name
        )
        _shutdown_event.set()

    # Register signal handlers (Unix only - Windows uses KeyboardInterrupt)
    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler, sig)


async def monitor_shutdown(bot: Bot) -> None:
    """Monitor for shutdown event and trigger cleanup."""
    await _shutdown_event.wait()

    logger = logging.getLogger(__name__)
    logger.info("Shutdown signal received, stopping bot...")

    # Stop polling
    await bot.session.close()

    # Trigger dispatcher shutdown
    raise SystemExit(0)


async def main() -> None:
    """Main bot entry point with graceful shutdown support."""
    setup_logging()
    logger = logging.getLogger(__name__)

    # Initialize Sentry
    setup_sentry()

    logger.info("Starting Telegram File Storage Bot — Enhanced Edition v2.0.0")
    logger.info("Environment: %s", settings.sentry_environment)

    # Create bot instance
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Get FSM storage (Redis or Memory fallback)
    fsm_storage = await connect_to_redis()
    logger.info("Using %s for FSM state storage",
                "Redis" if isinstance(fsm_storage, RedisStorage) else "Memory")

    # Create dispatcher
    dp = Dispatcher(
        storage=fsm_storage,
        events_on_shutdown=False,  # We'll handle shutdown ourselves
    )

    # Register lifecycle hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Middleware
    dp.update.outer_middleware(AllowlistMiddleware())

    # Routers — order matters (most specific first)
    dp.include_router(admin.router)
    dp.include_router(download.router)
    dp.include_router(upload.router)
    dp.include_router(common.router)  # catch-all last

    # Background tasks
    loop = asyncio.get_event_loop()

    # Setup signal handlers
    setup_signal_handlers(loop)

    # Create background task for expiry cleanup
    expiry_task = loop.create_task(expiry_warning_task(bot))

    # Create shutdown monitor task
    shutdown_monitor_task = None

    logger.info("Polling for updates...")

    try:
        # Start shutdown monitor
        shutdown_monitor_task = loop.create_task(monitor_shutdown(bot))

        # Start polling
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True,
        )
    except Exception as exc:
        logger.exception("Unhandled error during polling: %s", exc)
        raise
    finally:
        logger.info("Cleaning up...")

        # Cancel background tasks
        if expiry_task and not expiry_task.done():
            expiry_task.cancel()
            with suppress(asyncio.CancelledError):
                await expiry_task

        if shutdown_monitor_task and not shutdown_monitor_task.done():
            shutdown_monitor_task.cancel()
            with suppress(asyncio.CancelledError):
                await shutdown_monitor_task

        # Ensure bot session is closed
        await bot.session.close()

        logger.info("Main loop terminated.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Bot stopped by keyboard interrupt")
        sys.exit(0)
    except SystemExit as e:
        sys.exit(e.code)
    except Exception:
        logging.getLogger(__name__).exception("Fatal error during startup")
        sys.exit(1)
