"""
Pytest fixtures and shared test setup for the bot test suite.
"""
import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator, Generator

import pytest
from aiogram.types import Message, Update, User, Chat
from bson import ObjectId

from bot.models.file_record import FileRecord, UserQuotaRecord, PyObjectId


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_connection(event_loop: asyncio.AbstractEventLoop) -> AsyncGenerator:
    """
    In-memory MongoDB for testing.
    Note: In production, use mongomock or a separate test database.
    """
    from motor.motor_asyncio import AsyncIOMotorClient

    # Use in-memory MongoDB URI if available, otherwise use localhost test database
    client = AsyncIOMotorClient("mongodb://localhost:27017", serverSelectionTimeoutMS=5000)

    try:
        await client.admin.command("ping")

        # Create a test database
        test_db = client["tg_file_storage_test"]

        yield test_db

    except Exception:
        pytest.skip("MongoDB not available for testing")
    finally:
        # Cleanup test database
        try:
            await client.drop_database("tg_file_storage_test")
        except:
            pass
        client.close()


@pytest.fixture
def user_id() -> int:
    """Test user ID."""
    return 123456789


@pytest.fixture
def channel_id() -> int:
    """Test storage channel ID."""
    return -1001234567890


@pytest.fixture
def file_records(db_connection, user_id: int, channel_id: int) -> AsyncGenerator[list[FileRecord], None]:
    """Create sample file records for testing."""

    async def _create_records() -> list[FileRecord]:
        records = [
            FileRecord(
                user_id=user_id,
                username="testuser",
                original_filename="test_file.pdf",
                file_type="document",
                mime_type="application/pdf",
                file_size=1024 * 1024,  # 1 MB
                internal_message_id=1,
                channel_id=channel_id,
                telegram_file_id="file_id_1",
                telegram_file_unique_id="unique_id_1",
                caption="Test PDF file",
                tags=["test", "important"],
            ),
            FileRecord(
                user_id=user_id,
                username="testuser",
                original_filename="image.png",
                file_type="photo",
                mime_type="image/png",
                file_size=512 * 1024,  # 512 KB
                internal_message_id=2,
                channel_id=channel_id,
                telegram_file_id="file_id_2",
                telegram_file_unique_id="unique_id_2",
                tags=["image", "test"],
            ),
        ]

        # Insert into test database
        for record in records:
            await db_connection["files"].insert_one(record.to_mongo())

        return records

    records = asyncio.run(_create_records())
    yield records

    # Cleanup
    async def _cleanup():
        await db_connection["files"].delete_many({"user_id": user_id})

    asyncio.run(_cleanup())


@pytest.fixture
def file_record(db_connection, user_id: int, channel_id: int) -> FileRecord:
    """Create a single file record for testing."""
    return FileRecord(
        user_id=user_id,
        username="testuser",
        original_filename="test.txt",
        file_type="document",
        mime_type="text/plain",
        file_size=1024,
        internal_message_id=1,
        channel_id=channel_id,
        telegram_file_id="test_file_id",
        telegram_file_unique_id="test_unique_id",
    )


@pytest.fixture
def user_quota_record(user_id: int) -> UserQuotaRecord:
    """Create a user quota record for testing."""
    return UserQuotaRecord(
        user_id=user_id,
        bandwidth_limit=500 * 1024 * 1024,  # 500 MB
        download_limit=10,
        bandwidth_used=10 * 1024 * 1024,  # 10 MB
        download_count=2,
        quota_reset_time=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_message(user_id: int) -> Message:
    """Create a mock Telegram Message."""
    user = User(id=user_id, username="testuser", is_bot=False, first_name="Test")
    chat = Chat(id=user_id, type="private")

    # Create a minimal message
    return Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        from_user=user,
        chat=chat,
    )


@pytest.fixture
def mock_update(mock_message: Message) -> Update:
    """Create a mock Telegram Update."""
    return Update(
        update_id=1,
        message=mock_message,
    )


@pytest.fixture
def valid_object_id() -> ObjectId:
    """Create a valid ObjectId for testing."""
    return ObjectId()


@pytest.fixture
def invalid_object_id() -> str:
    """Create an invalid ObjectId string for testing."""
    return "invalid_id_123"
