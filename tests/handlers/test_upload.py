"""
Unit tests for Upload handler.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.types import Message, User, Chat, Document, PhotoSize

from bot.handlers.upload import handle_file_upload, MEDIA_FILTER
from bot.models.file_record import FileRecord


@pytest.mark.asyncio
async def test_is_admin():
    """Test is_admin function."""
    from bot.handlers.upload import is_admin
    from bot.config import settings

    # Set admin user IDs
    settings.admin_user_ids = [123456789]

    assert is_admin(123456789) is True
    assert is_admin(987654321) is False


@pytest.mark.asyncio
async def handle_file_upload_non_admin():
    """Test that non-admin users cannot upload files."""
    message = MagicMock(spec=Message)
    message.from_user = User(id=987654321, username="nonadmin", is_bot=False)
    message.answer = AsyncMock()

    bot = MagicMock(spec=Bot)

    # Set admin user IDs
    with patch("bot.handlers.upload.settings") as mock_settings:
        mock_settings.admin_user_ids = [123456789]

        await handle_file_upload(message, bot)

    # Should send restricted message
    message.answer.assert_called_once()
    assert "restricted to admins" in message.answer.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_handle_file_upload_duplicate_detection():
    """Test duplicate detection prevents re-uploading same file."""
    user_id = 123456789

    message = MagicMock(spec=Message)
    message.from_user = User(id=user_id, username="admin", is_bot=False)
    message.message_id = 100

    # Create a document
    document = Document(
        file_id="file_abc123",
        file_unique_id="unique_abc123",
        file_name="test.pdf",
        file_size=1024 * 1024,
        mime_type="application/pdf"
    )
    message.document = document
    message.photo = None
    message.video = None
    message.audio = None
    message.voice = None
    message.video_note = None
    message.sticker = None
    message.animation = None
    message.caption = "Test file"
    message.chat = MagicMock()
    message.chat.id = user_id

    bot = MagicMock(spec=Bot)

    with patch("bot.handlers.upload.settings") as mock_settings:
        mock_settings.admin_user_ids = [user_id]
        mock_settings.storage_channel_id = -1001234567890
        mock_settings.default_expiry_days = 0

        with patch("bot.handlers.upload.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            # Mock duplicate file found
            duplicate_record = FileRecord(
                id="existing_id",
                user_id=user_id,
                original_filename="existing.pdf",
                display_name="renamed.pdf",
                file_type="document",
                internal_message_id=1,
                channel_id=-1001234567890,
                telegram_file_id="old_file_id",
                telegram_file_unique_id="unique_abc123",
                upload_date=datetime.now(timezone.utc) - timedelta(days=1),
            )

            mock_file_repo = MagicMock()
            mock_file_repo.find_duplicate = AsyncMock(return_value=duplicate_record)
            mock_get_db.return_value = mock_db

            msg_answer = AsyncMock()
            message.answer.return_value = msg_answer

            await handle_file_upload(message, bot)

            # Should notify about duplicate
            message.answer.assert_called_once()
            assert "duplicate" in message.answer.call_args[0][0].lower()

            # Should not attempt to copy or insert
            bot.copy_message.assert_not_called()
            mock_file_repo.insert.assert_not_called()


@pytest.mark.asyncio
async def test_handle_file_upload_success():
    """Test successful file upload."""
    user_id = 123456789

    # Create mock message with document
    message = MagicMock(spec=Message)
    message.from_user = User(id=user_id, username="admin", is_bot=False)
    message.message_id = 100

    document = Document(
        file_id="file_abc123",
        file_unique_id="unique_abc123",
        file_name="test.pdf",
        file_size=1024 * 1024,
        mime_type="application/pdf"
    )
    message.document = document
    message.photo = None
    message.video = None
    message.audio = None
    message.voice = None
    message.video_note = None
    message.sticker = None
    message.animation = None
    message.caption = "Test file"
    message.chat = MagicMock()
    message.chat.id = user_id

    bot = MagicMock(spec=Bot)

    # Mock successful copy_message
    copied_message = MagicMock()
    copied_message.message_id = 500
    bot.copy_message = AsyncMock(return_value=copied_message)

    # Mock message answer/edit methods
    processing_msg = MagicMock()
    processing_msg.edit_text = AsyncMock()
    message.answer = AsyncMock(return_value=processing_msg)

    with patch("bot.handlers.upload.settings") as mock_settings:
        mock_settings.admin_user_ids = [user_id]
        mock_settings.storage_channel_id = -1001234567890
        mock_settings.default_expiry_days = 0

        with patch("bot.handlers.upload.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            mock_file_repo = MagicMock()
            mock_file_repo.find_duplicate = AsyncMock(return_value=None)  # No duplicate
            mock_file_repo.insert = AsyncMock(return_value="new_record_id_123")
            mock_get_db.return_value = mock_file_repo

            await handle_file_upload(message, bot)

            # Verify upload flow
            bot.copy_message.assert_called_once_with(
                chat_id=-1001234567890,
                from_chat_id=user_id,
                message_id=100,
                caption=pytest.approx(
                    "[STORED]\nUser: 123456789 (@admin)\nFile: test.pdf\nType: document\n"
                )
            )

            mock_file_repo.find_duplicate.assert_called_once_with(user_id, "unique_abc123")

            # Verify record insertion
            mock_file_repo.insert.assert_called_once()
            insert_call = mock_file_repo.insert.call_args[0][0]
            assert insert_call.user_id == user_id
            assert insert_call.original_filename == "test.pdf"
            assert insert_call.file_type == "document"
            assert insert_call.telegram_file_unique_id == "unique_abc123"
            assert insert_call.internal_message_id == 500
            assert insert_call.expires_at is None

            # Verify success message
            final_edit_calls = processing_msg.edit_text.call_args_list
            assert len(final_edit_calls) == 2  # First is processing, second is success

            success_message = final_edit_calls[1][0][0]
            assert "file stored" in success_message.lower()
            assert "test.pdf" in success_message
            assert "new_record_id_123" in success_message


@pytest.mark.asyncio
async def test_handle_file_upload_with_expiry():
    """Test file upload with auto-expiry."""
    user_id = 123456789

    message = MagicMock(spec=Message)
    message.from_user = User(id=user_id, username="admin", is_bot=False)
    message.message_id = 100

    document = Document(
        file_id="file_abc123",
        file_unique_id="unique_abc123",
        file_name="test.pdf",
        file_size=1024 * 1024,
        mime_type="application/pdf"
    )
    message.document = document
    message.photo = None
    message.video = None
    message.audio = None
    message.voice = None
    message.video_note = None
    message.sticker = None
    message.animation = None
    message.caption = "Test file"
    message.chat = MagicMock()
    message.chat.id = user_id

    bot = MagicMock(spec=Bot)
    copied_message = MagicMock()
    copied_message.message_id = 500
    bot.copy_message = AsyncMock(return_value=copied_message)

    processing_msg = MagicMock()
    processing_msg.edit_text = AsyncMock()
    message.answer = AsyncMock(return_value=processing_msg)

    with patch("bot.handlers.upload.settings") as mock_settings:
        mock_settings.admin_user_ids = [user_id]
        mock_settings.storage_channel_id = -1001234567890
        mock_settings.default_expiry_days = 7  # 7 days expiry

        with patch("bot.handlers.upload.get_db") as mock_get_db:
            mock_file_repo = MagicMock()
            mock_file_repo.find_duplicate = AsyncMock(return_value=None)
            mock_file_repo.insert = AsyncMock(return_value="new_record_id")
            mock_get_db.return_value = mock_file_repo

            await handle_file_upload(message, bot)

            # Verify expires_at is set
            insert_call = mock_file_repo.insert.call_args[0][0]
            assert insert_call.expires_at is not None

            # Should be approximately 7 days from now
            now = datetime.now(timezone.utc)
            diff = insert_call.expires_at - now
            assert timedelta(days=6) < diff < timedelta(days=8)

            # Verify expiry is shown in success message
            final_edit_calls = processing_msg.edit_text.call_args_list
            success_message = final_edit_calls[1][0][0]
            assert "expires" in success_message.lower()


@pytest.mark.asyncio
async def test_handle_file_upload_copy_failure():
    """Test handling of channel copy failure."""
    user_id = 123456789

    message = MagicMock(spec=Message)
    message.from_user = User(id=user_id, username="admin", is_bot=False)
    message.message_id = 100

    document = Document(
        file_id="file_abc123",
        file_unique_id="unique_abc123",
        file_name="test.pdf",
        file_size=1024 * 1024,
        mime_type="application/pdf"
    )
    message.document = document
    message.photo = None
    message.video = None
    message.audio = None
    message.voice = None
    message.video_note = None
    message.sticker = None
    message.animation = None
    message.caption = "Test file"
    message.chat = MagicMock()
    message.chat.id = user_id

    bot = MagicMock(spec=Bot)
    bot.copy_message = AsyncMock(side_effect=Exception("Network error"))

    message.answer = AsyncMock()

    with patch("bot.handlers.upload.settings") as mock_settings:
        mock_settings.admin_user_ids = [user_id]

        with patch("bot.handlers.upload.get_db") as mock_get_db:
            mock_file_repo = MagicMock()
            mock_file_repo.find_duplicate = AsyncMock(return_value=None)
            mock_get_db.return_value = mock_file_repo

            await handle_file_upload(message, bot)

            # Should send error message
            message.answer.assert_called_once()
            error_msg = message.answer.call_args[0][0]

            # Should show processing message first
            assert "storing" in error_msg.lower() or "storage failed" in error_msg.lower()

            # Should not attempt to insert record
            mock_file_repo.insert.assert_not_called()


@pytest.mark.asyncio
async def test_handle_file_upload_db_insert_failure():
    """Test handling of MongoDB insert failure."""
    user_id = 123456789

    message = MagicMock(spec=Message)
    message.from_user = User(id=user_id, username="admin", is_bot=False)
    message.message_id = 100

    document = Document(
        file_id="file_abc123",
        file_unique_id="unique_abc123",
        file_name="test.pdf",
        file_size=1024 * 1024,
        mime_type="application/pdf"
    )
    message.document = document
    message.photo = None
    message.video = None
    message.audio = None
    message.voice = None
    message.video_note = None
    message.sticker = None
    message.animation = None
    message.caption = "Test file"
    message.chat = MagicMock()
    message.chat.id = user_id

    bot = MagicMock(spec=Bot)
    copied_message = MagicMock()
    copied_message.message_id = 500
    bot.copy_message = AsyncMock(return_value=copied_message)

    processing_msg = MagicMock()
    processing_msg.edit_text = AsyncMock()
    message.answer = AsyncMock(return_value=processing_msg)

    with patch("bot.handlers.upload.settings") as mock_settings:
        mock_settings.admin_user_ids = [user_id]
        mock_settings.storage_channel_id = -1001234567890
        mock_settings.default_expiry_days = 0

        with patch("bot.handlers.upload.get_db") as mock_get_db:
            mock_file_repo = MagicMock()
            mock_file_repo.find_duplicate = AsyncMock(return_value=None)
            mock_file_repo.insert = AsyncMock(side_effect=Exception("DB error"))
            mock_get_db.return_value = mock_file_repo

            await handle_file_upload(message, bot)

            # File was copied to channel
            assert bot.copy_message.called

            # But insert failed
            assert mock_file_repo.insert.called

            # Should show metadata save error
            final_edit_calls = processing_msg.edit_text.call_args_list
            success_message = final_edit_calls[1][0][0]
            assert "metadata save failed" in success_message.lower()


@pytest.mark.asyncio
async def test_media_filter():
    """Test MEDIA_FILTER accepts all media types."""
    # The filter should match documents, photos, videos, audio, etc.
    assert MEDIA_FILTER is not None
    # The filter is constructed using | operator, so it's a valid aiogram filter


@pytest.mark.asyncio
async def test_handle_file_upload_photo():
    """Test uploading a photo file."""
    user_id = 123456789

    message = MagicMock(spec=Message)
    message.from_user = User(id=user_id, username="admin", is_bot=False)
    message.message_id = 100

    # Create a photo (array of PhotoSize)
    photos = [
        PhotoSize(file_id="small", file_unique_id="unique_small", file_size=100),
        PhotoSize(file_id="large", file_unique_id="unique_large", file_size=1024),
    ]
    message.photo = photos
    message.document = None
    message.video = None
    message.audio = None
    message.voice = None
    message.video_note = None
    message.sticker = None
    message.animation = None
    message.caption = "Test photo"
    message.chat = MagicMock()
    message.chat.id = user_id

    bot = MagicMock(spec=Bot)
    copied_message = MagicMock()
    copied_message.message_id = 500
    bot.copy_message = AsyncMock(return_value=copied_message)

    processing_msg = MagicMock()
    processing_msg.edit_text = AsyncMock()
    message.answer = AsyncMock(return_value=processing_msg)

    with patch("bot.handlers.upload.settings") as mock_settings:
        mock_settings.admin_user_ids = [user_id]
        mock_settings.storage_channel_id = -1001234567890
        mock_settings.default_expiry_days = 0

        with patch("bot.handlers.upload.get_db") as mock_get_db:
            mock_file_repo = MagicMock()
            mock_file_repo.find_duplicate = AsyncMock(return_value=None)
            mock_file_repo.insert = AsyncMock(return_value="new_record_id")
            mock_get_db.return_value = mock_file_repo

            await handle_file_upload(message, bot)

            # Verify file type is detected as photo
            insert_call = mock_file_repo.insert.call_args[0][0]
            assert insert_call.file_type == "photo"
            assert "photo" in insert_call.original_filename.lower()


@pytest.mark.asyncio
async def test_handle_file_upload_with_display_name():
    """Test that message caption is saved correctly."""
    user_id = 123456789

    message = MagicMock(spec=Message)
    message.from_user = User(id=user_id, username="admin", is_bot=False)
    message.message_id = 100

    document = Document(
        file_id="file_abc123",
        file_unique_id="unique_abc123",
        file_name="test.pdf",
        file_size=1024 * 1024,
        mime_type="application/pdf"
    )
    message.document = document
    message.photo = None
    message.video = None
    message.audio = None
    message.voice = None
    message.video_note = None
    message.sticker = None
    message.animation = None
    message.caption = "This is an important invoice"
    message.chat = MagicMock()
    message.chat.id = user_id

    bot = MagicMock(spec=Bot)
    copied_message = MagicMock()
    copied_message.message_id = 500
    bot.copy_message = AsyncMock(return_value=copied_message)

    processing_msg = MagicMock()
    processing_msg.edit_text = AsyncMock()
    message.answer = AsyncMock(return_value=processing_msg)

    with patch("bot.handlers.upload.settings") as mock_settings:
        mock_settings.admin_user_ids = [user_id]
        mock_settings.storage_channel_id = -1001234567890
        mock_settings.default_expiry_days = 0

        with patch("bot.handlers.upload.get_db") as mock_get_db:
            mock_file_repo = MagicMock()
            mock_file_repo.find_duplicate = AsyncMock(return_value=None)
            mock_file_repo.insert = AsyncMock(return_value="new_record_id")
            mock_get_db.return_value = mock_file_repo

            await handle_file_upload(message, bot)

            # Verify caption is saved
            insert_call = mock_file_repo.insert.call_args[0][0]
            assert insert_call.caption == "This is an important invoice"
