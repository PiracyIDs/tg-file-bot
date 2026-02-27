"""
Unit tests for FileRecord and UserQuotaRecord models.
"""
import pytest
from datetime import datetime, timedelta, timezone
from pydantic import ValidationError

from bot.models.file_record import FileRecord, UserQuotaRecord, PyObjectId, generate_share_code


def test_file_record_creation():
    """Test creating a FileRecord."""
    record = FileRecord(
        user_id=123456789,
        username="testuser",
        original_filename="test.pdf",
        file_type="document",
        mime_type="application/pdf",
        file_size=1024 * 1024,
        internal_message_id=1,
        channel_id=-1001234567890,
        telegram_file_id="file_id_123",
        telegram_file_unique_id="unique_id_123",
    )

    assert record.user_id == 123456789
    assert record.username == "testuser"
    assert record.original_filename == "test.pdf"
    assert record.file_type == "document"
    assert record.file_size == 1024 * 1024
    assert record.tags == []
    assert record.upload_date is not None


def test_file_record_with_tags():
    """Test creating a FileRecord with tags."""
    record = FileRecord(
        user_id=123456789,
        original_filename="test.pdf",
        file_type="document",
        internal_message_id=1,
        channel_id=-1001234567890,
        telegram_file_id="file_id_123",
        telegram_file_unique_id="unique_id_123",
        tags=["invoice", "2024", "important"],
    )

    assert len(record.tags) == 3
    assert "invoice" in record.tags
    assert "2024" in record.tags
    assert "important" in record.tags


def test_file_record_with_expiry():
    """Test creating a FileRecord with expiry."""
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    record = FileRecord(
        user_id=123456789,
        original_filename="test.pdf",
        file_type="document",
        internal_message_id=1,
        channel_id=-1001234567890,
        telegram_file_id="file_id_123",
        telegram_file_unique_id="unique_id_123",
        expires_at=expires_at,
    )

    assert record.expires_at is not None
    assert record.expires_at == expires_at


def test_file_record_effective_name():
    """Test effective_name property."""
    # When display_name is set, it should return display_name
    record = FileRecord(
        user_id=123456789,
        original_filename="original.pdf",
        file_type="document",
        internal_message_id=1,
        channel_id=-1001234567890,
        telegram_file_id="file_id_123",
        telegram_file_unique_id="unique_id_123",
        display_name="renamed.pdf",
    )

    assert record.effective_name == "renamed.pdf"

    # When display_name is None, it should return original_filename
    record2 = FileRecord(
        user_id=123456789,
        original_filename="original.pdf",
        file_type="document",
        internal_message_id=1,
        channel_id=-1001234567890,
        telegram_file_id="file_id_123",
        telegram_file_unique_id="unique_id_123",
    )

    assert record2.effective_name == "original.pdf"


def test_file_record_to_mongo():
    """Test converting FileRecord to MongoDB document."""
    record = FileRecord(
        user_id=123456789,
        original_filename="test.pdf",
        file_type="document",
        internal_message_id=1,
        channel_id=-1001234567890,
        telegram_file_id="file_id_123",
        telegram_file_unique_id="unique_id_123",
        tags=["test"],
        display_name="renamed.pdf",
    )

    doc = record.to_mongo()

    assert doc["user_id"] == 123456789
    assert doc["original_filename"] == "test.pdf"
    assert doc["tags"] == ["test"]
    assert doc["display_name"] == "renamed.pdf"
    assert "_id" not in doc  # Should not have _id when not set


def test_file_record_to_mongo_with_id():
    """Test converting FileRecord to MongoDB document with _id."""
    from bson import ObjectId

    record = FileRecord(
        id="507f1f77bcf86cd799439011",
        user_id=123456789,
        original_filename="test.pdf",
        file_type="document",
        internal_message_id=1,
        channel_id=-1001234567890,
        telegram_file_id="file_id_123",
        telegram_file_unique_id="unique_id_123",
    )

    doc = record.to_mongo()

    assert "_id" in doc
    assert isinstance(doc["_id"], ObjectId)
    assert str(doc["_id"]) == "507f1f77bcf86cd799439011"


def test_user_quota_record_creation():
    """Test creating a UserQuotaRecord."""
    record = UserQuotaRecord(
        user_id=123456789,
        bandwidth_limit=500 * 1024 * 1024,
        download_limit=10,
    )

    assert record.user_id == 123456789
    assert record.bandwidth_limit == 500 * 1024 * 1024
    assert record.download_limit == 10
    assert record.bandwidth_used == 0
    assert record.download_count == 0


def test_user_quota_record_is_unlimited():
    """Test is_unlimited property."""
    # Zero bandwidth limit means unlimited
    unlimited = UserQuotaRecord(
        user_id=123456789,
        bandwidth_limit=0,
        download_limit=10,
    )

    assert unlimited.is_unlimited is True

    # Non-zero bandwidth limit means limited
    limited = UserQuotaRecord(
        user_id=123456789,
        bandwidth_limit=500 * 1024 * 1024,
        download_limit=10,
    )

    assert limited.is_unlimited is False


def test_user_quota_record_bandwidth_remaining():
    """Test bandwidth_remaining property."""
    record = UserQuotaRecord(
        user_id=123456789,
        bandwidth_limit=100 * 1024 * 1024,
        download_limit=10,
        bandwidth_used=20 * 1024 * 1024,
    )

    assert record.bandwidth_remaining == 80 * 1024 * 1024

    # Test when unlimited
    unlimited = UserQuotaRecord(
        user_id=123456789,
        bandwidth_limit=0,
        download_limit=10,
    )

    assert unlimited.bandwidth_remaining == float("inf")


def test_user_quota_record_downloads_remaining():
    """Test downloads_remaining property."""
    record = UserQuotaRecord(
        user_id=123456789,
        bandwidth_limit=100 * 1024 * 1024,
        download_limit=10,
        download_count=3,
    )

    assert record.downloads_remaining == 7

    # Test when unlimited
    unlimited = UserQuotaRecord(
        user_id=123456789,
        bandwidth_limit=100 * 1024 * 1024,
        download_limit=0,
    )

    assert unlimited.downloads_remaining == float("inf")


def test_user_quota_record_to_mongo():
    """Test converting UserQuotaRecord to MongoDB document."""
    record = UserQuotaRecord(
        user_id=123456789,
        bandwidth_limit=500 * 1024 * 1024,
        download_limit=10,
        bandwidth_used=10 * 1024 * 1024,
        download_count=2,
    )

    doc = record.to_mongo()

    assert doc["user_id"] == 123456789
    assert doc["bandwidth_limit"] == 500 * 1024 * 1024
    assert doc["download_limit"] == 10
    assert doc["bandwidth_used"] == 10 * 1024 * 1024
    assert doc["download_count"] == 2


def test_pyobject_id_validation_valid():
    """Test PyObjectId with valid ObjectId."""
    from bson import ObjectId

    object_id = ObjectId()
    py_object_id = PyObjectId(str(object_id))

    assert str(py_object_id) == str(object_id)


def test_pyobject_id_validation_invalid():
    """Test PyObjectId with invalid ObjectId."""
    with pytest.raises(ValueError, match="Invalid ObjectId"):
        PyObjectId("invalid_id")


def test_generate_share_code():
    """Test share code generation."""
    code = generate_share_code()

    # Default length is 8
    assert len(code) == 8
    assert code.isupper()
    assert code.isalnum()

    # Test with custom length
    code12 = generate_share_code(12)
    assert len(code12) == 12
    assert code12.isupper()
    assert code12.isalnum()

    # Test codes are unique
    code1 = generate_share_code(16)
    code2 = generate_share_code(16)
    assert code1 != code2


def test_user_quota_record_with_verify_status():
    """Test UserQuotaRecord with verification status."""
    now = datetime.now(timezone.utc)

    record = UserQuotaRecord(
        user_id=123456789,
        bandwidth_limit=500 * 1024 * 1024,
        download_limit=10,
        is_verified=True,
        verify_token="abc123xyz",
        verified_time=now,
        verify_count=5,
    )

    assert record.is_verified is True
    assert record.verify_token == "abc123xyz"
    assert record.verified_time == now
    assert record.verify_count == 5
