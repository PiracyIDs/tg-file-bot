"""
Unit tests for file_utils functions.
"""
import pytest
from unittest.mock import AsyncMock, patch

from bot.utils.file_utils import (
    detect_file_type,
    extract_file_info,
    format_size,
    parse_tags,
    get_exp_time,
)
from aiogram.types import Message, User, Chat


def test_detect_file_type_document():
    """Test detecting document file type."""
    message = Message(
        message_id=1,
        date=None,
        from_user=None,
        chat=None,
        document={"file_name": "test.pdf", "file_id": "123", "file_unique_id": "unique123"}
    )

    assert detect_file_type(message) == "document"


def test_detect_file_type_photo():
    """Test detecting photo file type."""
    message = Message(
        message_id=1,
        date=None,
        from_user=None,
        chat=None,
        photo=[{"file_id": "123", "file_unique_id": "unique123", "file_size": 1024}]
    )

    assert detect_file_type(message) == "photo"


def test_detect_file_type_video():
    """Test detecting video file type."""
    message = Message(
        message_id=1,
        date=None,
        from_user=None,
        chat=None,
        video={"file_name": "test.mp4", "file_id": "123", "file_unique_id": "unique123"}
    )

    assert detect_file_type(message) == "video"


def test_detect_file_type_audio():
    """Test detecting audio file type."""
    message = Message(
        message_id=1,
        date=None,
        from_user=None,
        chat=None,
        audio={"file_name": "test.mp3", "file_id": "123", "file_unique_id": "unique123"}
    )

    assert detect_file_type(message) == "audio"


def test_detect_file_type_voice():
    """Test detecting voice file type."""
    message = Message(
        message_id=1,
        date=None,
        from_user=None,
        chat=None,
        voice={"file_id": "123", "file_unique_id": "unique123", "file_size": 1024}
    )

    assert detect_file_type(message) == "voice"


def test_detect_file_type_sticker():
    """Test detecting sticker file type."""
    message = Message(
        message_id=1,
        date=None,
        from_user=None,
        chat=None,
        sticker={"file_id": "123", "file_unique_id": "unique123"}
    )

    assert detect_file_type(message) == "sticker"


def test_extract_file_info_document():
    """Test extracting file info from document."""
    message = Message(
        message_id=1,
        date=None,
        from_user=None,
        chat=None,
        document={
            "file_name": "test.pdf",
            "file_id": "file_id_123",
            "file_unique_id": "unique_id_123",
            "file_size": 1024 * 500,
            "mime_type": "application/pdf"
        }
    )

    filename, file_id, file_unique_id, file_size, mime_type = extract_file_info(message)

    assert filename == "test.pdf"
    assert file_id == "file_id_123"
    assert file_unique_id == "unique_id_123"
    assert file_size == 512000
    assert mime_type == "application/pdf"


def test_extract_file_info_photo():
    """Test extracting file info from photo."""
    message = Message(
        message_id=1,
        date=None,
        from_user=None,
        chat=None,
        photo=[
            {"file_id": "small", "file_unique_id": "small_unique", "file_size": 100},
            {"file_id": "large", "file_unique_id": "large_unique", "file_size": 1024}
        ]
    )

    filename, file_id, file_unique_id, file_size, mime_type = extract_file_info(message)

    assert "photo_large_unique.jpg" in filename
    assert file_id == "large"
    assert file_unique_id == "large_unique"
    assert file_size == 1024
    assert mime_type == "image/jpeg"


def test_extract_file_info_video():
    """Test extracting file info from video."""
    message = Message(
        message_id=1,
        date=None,
        from_user=None,
        chat=None,
        video={
            "file_name": "test.mp4",
            "file_id": "file_id_123",
            "file_unique_id": "unique_id_123",
            "file_size": 1024 * 1024 * 10,
            "mime_type": "video/mp4"
        }
    )

    filename, file_id, file_unique_id, file_size, mime_type = extract_file_info(message)

    assert filename == "test.mp4"
    assert file_id == "file_id_123"
    assert file_unique_id == "unique_id_123"
    assert file_size == 10485760
    assert mime_type == "video/mp4"


def test_extract_file_info_audio():
    """Test extracting file info from audio."""
    message = Message(
        message_id=1,
        date=None,
        from_user=None,
        chat=None,
        audio={
            "performer": "Artist",
            "title": "Song Title",
            "file_id": "file_id_123",
            "file_unique_id": "unique_id_123",
            "file_size": 1024 * 5,
            "mime_type": "audio/mpeg"
        }
    )

    filename, file_id, file_unique_id, file_size, mime_type = extract_file_info(message)

    assert filename == "Artist - Song Title.mp3"
    assert file_id == "file_id_123"
    assert file_unique_id == "unique_id_123"
    assert file_size == 5120
    assert mime_type == "audio/mpeg"


def test_format_size_bytes():
    """Test formatting size in bytes."""
    assert format_size(512) == "512.0 B"
    assert format_size(1023) == "1023.0 B"


def test_format_size_kilobytes():
    """Test formatting size in kilobytes."""
    assert format_size(1024) == "1.0 KB"
    assert format_size(1536) == "1.5 KB"
    assert format_size(100 * 1024) == "100.0 KB"


def test_format_size_megabytes():
    """Test formatting size in megabytes."""
    assert format_size(1024 * 1024) == "1.0 MB"
    assert format_size(512 * 1024 * 1024) == "512.0 MB"
    assert format_size(100 * 1024 * 1024) == "100.0 MB"


def test_format_size_gigabytes():
    """Test formatting size in gigabytes."""
    assert format_size(1024 * 1024 * 1024) == "1.0 GB"
    assert format_size(2 * 1024 * 1024 * 1024) == "2.0 GB"


def test_format_size_terabytes():
    """Test formatting size in terabytes."""
    assert format_size(1024 * 1024 * 1024 * 1024) == "1.0 TB"


def test_format_size_none():
    """Test formatting size when None."""
    assert format_size(None) == "Unknown"


def test_parse_tags_with_hash():
    """Test parsing tags with # prefix."""
    tags = parse_tags("#invoice #2024 #work")

    assert len(tags) == 3
    assert "invoice" in tags
    assert "2024" in tags
    assert "work" in tags


def test_parse_tags_without_hash():
    """Test parsing tags without # prefix."""
    tags = parse_tags("invoice 2024 work")

    assert len(tags) == 3
    assert "invoice" in tags
    assert "2024" in tags
    assert "work" in tags


def test_parse_tags_mixed():
    """Test parsing tags with mixed # prefix."""
    tags = parse_tags("#invoice 2024 #work")

    assert len(tags) == 3
    assert "invoice" in tags
    assert "2024" in tags
    assert "work" in tags


def test_parse_tags_case_insensitive():
    """Test that tags are normalized to lowercase."""
    tags = parse_tags("#INVOICE #2024 #WORK")

    assert tags == ["invoice", "2024", "work"]


def test_parse_tags_empty():
    """Test parsing empty string."""
    tags = parse_tags("")

    assert tags == []


def test_parse_tags_whitespace():
    """Test parsing tags with extra whitespace."""
    tags = parse_tags("  #invoice  #2024  #work  ")

    assert tags == ["invoice", "2024", "work"]


def test_get_exp_time_seconds():
    """Test getting expiration time for seconds."""
    assert get_exp_time(30) == "30 secs"
    assert get_exp_time(59) == "59 secs"


def test_get_exp_time_minutes():
    """Test getting expiration time for minutes."""
    assert get_exp_time(60) == "1 mins"
    assert get_exp_time(120) == "2 mins"
    assert get_exp_time(3600) == "60 mins"


def test_get_exp_time_hours():
    """Test getting expiration time for hours."""
    assert get_exp_time(3600) == "1 hours"
    assert get_exp_time(7200) == "2 hours"
    assert get_exp_time(86400) == "24 hours"


def test_get_exp_time_days():
    """Test getting expiration time for days."""
    assert get_exp_time(86400) == "1 days"
    assert get_exp_time(172800) == "2 days"
    assert get_exp_time(259200) == "3 days"


def test_get_exp_time_mixed():
    """Test getting expiration time with mixed units."""
    # 1 day, 2 hours, 30 minutes, 45 seconds
    # 86400 + 7200 + 1800 + 45 = 95445
    result = get_exp_time(95445)

    assert "1 days" in result
    assert "2 hours" in result
    assert "30 mins" in result
    assert "45 secs" in result


def test_get_exp_time_zero():
    """Test getting expiration time for zero seconds."""
    assert get_exp_time(0) == ""


@pytest.mark.asyncio
async def test_get_shortlink_no_config():
    """Test shortlink generation when config is missing."""
    result = await get_shortlink("", "", "https://example.com")

    assert result == "https://example.com"


@pytest.mark.asyncio
async def test_get_shortlink_with_config():
    """Test shortlink generation with config."""
    with patch("bot.utils.file_utils.Shortzy") as mock_shortzy_class:
        mock_shortzy = AsyncMock()
        mock_shortzy.convert = AsyncMock(return_value="https://short.ly/abc123")
        mock_shortzy_class.return_value = mock_shortzy

        result = await get_shortlink("linkshortify.com", "api_key", "https://example.com")

        assert result == "https://short.ly/abc123"
        mock_shortzy_class.assert_called_once_with(api_key="api_key", base_site="linkshortify.com")
        mock_shortzy.convert.assert_called_once_with("https://example.com")
