"""
Unit tests for FileRepository.
"""
import pytest
from bson import ObjectId

from bot.database.repositories.file_repo import FileRepository
from bot.models.file_record import FileRecord


@pytest.mark.asyncio
async def test_insert_file(db_connection, file_record: FileRecord):
    """Test inserting a new file record."""
    repo = FileRepository(db_connection)

    record_id = await repo.insert(file_record)

    assert record_id is not None
    assert ObjectId.is_valid(record_id)

    # Verify the file was inserted
    retrieved = await repo.get_by_id(record_id)
    assert retrieved is not None
    assert retrieved.original_filename == "test.txt"


@pytest.mark.asyncio
async def test_find_duplicate(db_connection, file_record: FileRecord, user_id: int):
    """Test finding duplicate files based on telegram_file_unique_id."""
    repo = FileRepository(db_connection)

    # Insert a file
    record_id = await repo.insert(file_record)

    # Try to find duplicate
    duplicate = await repo.find_duplicate(user_id, "test_unique_id")

    assert duplicate is not None
    assert duplicate.original_filename == "test.txt"
    assert duplicate.id == record_id

    # Non-existent file should return None
    no_duplicate = await repo.find_duplicate(user_id, "non_existent_unique_id")
    assert no_duplicate is None


@pytest.mark.asyncio
async def test_get_by_id(db_connection, file_record: FileRecord):
    """Test retrieving a file by ID."""
    repo = FileRepository(db_connection)

    record_id = await repo.insert(file_record)
    retrieved = await repo.get_by_id(record_id)

    assert retrieved is not None
    assert retrieved.id == record_id
    assert retrieved.original_filename == "test.txt"
    assert retrieved.file_type == "document"


@pytest.mark.asyncio
async def test_get_by_id_invalid(db_connection):
    """Test retrieving a file with invalid ID."""
    repo = FileRepository(db_connection)

    retrieved = await repo.get_by_id("invalid_id")
    assert retrieved is None

    retrieved = await repo.get_by_id("000000000000000000000000")
    assert retrieved is None


@pytest.mark.asyncio
async def test_list_by_user(db_connection, file_records: list[FileRecord], user_id: int):
    """Test listing files by user with pagination."""
    repo = FileRepository(db_connection)

    # Get first page (8 records per page, but we only have 2)
    records = await repo.list_by_user(user_id, page=1, page_size=8)

    assert len(records) == 2
    assert all(r.user_id == user_id for r in records)

    # Verify sorting by upload_date (desc)
    assert records[0].upload_date >= records[1].upload_date


@pytest.mark.asyncio
async def test_list_by_user_empty(db_connection, user_id: int):
    """Test listing files when user has no files."""
    repo = FileRepository(db_connection)

    # Use a different user_id that has no files
    records = await repo.list_by_user(999999, page=1, page_size=8)

    assert len(records) == 0


@pytest.mark.asyncio
async def test_count_by_user(db_connection, file_records: list[FileRecord], user_id: int):
    """Test counting files by user."""
    repo = FileRepository(db_connection)

    count = await repo.count_by_user(user_id)

    assert count == 2


@pytest.mark.asyncio
async def test_search_by_filename(db_connection, file_records: list[FileRecord], user_id: int):
    """Test searching files by filename (case-insensitive)."""
    repo = FileRepository(db_connection)

    # Search for "test" (case-insensitive)
    records = await repo.search_by_filename(user_id, "test")

    assert len(records) == 1  # Only test_file.pdf matches

    # Search for "FILE" (case-insensitive)
    records = await repo.search_by_filename(user_id, "FILE")

    assert len(records) >= 1


@pytest.mark.asyncio
async def test_search_by_tag(db_connection, file_records: list[FileRecord], user_id: int):
    """Test searching files by tag."""
    repo = FileRepository(db_connection)

    # Search for "test" tag
    records = await repo.search_by_tag(user_id, "test")

    assert len(records) == 2  # Both records have "test" tag

    # Search for "important" tag
    records = await repo.search_by_tag(user_id, "important")

    assert len(records) == 1  # Only first record has "important" tag


@pytest.mark.asyncio
async def test_rename(db_connection, file_record: FileRecord, user_id: int):
    """Test renaming a file."""
    repo = FileRepository(db_connection)

    record_id = await repo.insert(file_record)

    # Rename the file
    success = await repo.rename(record_id, user_id, "renamed_file.txt")

    assert success is True

    # Verify the rename
    retrieved = await repo.get_by_id(record_id)
    assert retrieved.display_name == "renamed_file.txt"
    assert retrieved.original_filename == "test.txt"  # Original unchanged


@pytest.mark.asyncio
async def test_rename_invalid_id(db_connection, user_id: int):
    """Test renaming with invalid ID."""
    repo = FileRepository(db_connection)

    success = await repo.rename("invalid_id", user_id, "new_name.txt")
    assert success is False


@pytest.mark.asyncio
async def test_set_tags(db_connection, file_record: FileRecord, user_id: int):
    """Test setting tags for a file."""
    repo = FileRepository(db_connection)

    record_id = await repo.insert(file_record)

    # Set tags
    success = await repo.set_tags(record_id, user_id, ["new_tag", "another_tag"])

    assert success is True

    # Verify tags
    retrieved = await repo.get_by_id(record_id)
    assert "new_tag" in retrieved.tags
    assert "another_tag" in retrieved.tags


@pytest.mark.asyncio
async def test_set_expiry(db_connection, file_record: FileRecord, user_id: int):
    """Test setting expiry for a file."""
    from datetime import timedelta
    repo = FileRepository(db_connection)

    record_id = await repo.insert(file_record)

    # Set expiry to 7 days
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    success = await repo.set_expiry(record_id, user_id, expires_at)

    assert success is True

    # Verify expiry
    retrieved = await repo.get_by_id(record_id)
    assert retrieved.expires_at is not None

    # Remove expiry
    success = await repo.set_expiry(record_id, user_id, None)
    assert success is True

    retrieved = await repo.get_by_id(record_id)
    assert retrieved.expires_at is None


@pytest.mark.asyncio
async def test_create_or_get_share_code(db_connection, file_record: FileRecord, user_id: int):
    """Test creating or retrieving a share code."""
    repo = FileRepository(db_connection)

    record_id = await repo.insert(file_record)

    # Create share code
    code = await repo.create_or_get_share_code(record_id, user_id)

    assert code is not None
    assert len(code) == 8  # Default length

    # Retrieve existing share code
    code2 = await repo.create_or_get_share_code(record_id, user_id)
    assert code2 == code  # Should return the same code


@pytest.mark.asyncio
async def test_get_by_share_code(db_connection, file_record: FileRecord, user_id: int):
    """Test retrieving a file by share code."""
    repo = FileRepository(db_connection)

    record_id = await repo.insert(file_record)
    code = await repo.create_or_get_share_code(record_id, user_id)

    # Get by share code
    retrieved = await repo.get_by_share_code(code)

    assert retrieved is not None
    assert retrieved.id == record_id


@pytest.mark.asyncio
async def test_increment_share_uses(db_connection, file_record: FileRecord, user_id: int):
    """Test incrementing share code uses."""
    repo = FileRepository(db_connection)

    record_id = await repo.insert(file_record)
    await repo.create_or_get_share_code(record_id, user_id)

    # Increment uses
    await repo.increment_share_uses(record_id)

    # Verify increment
    retrieved = await repo.get_by_id(record_id)
    assert retrieved.share_code_uses == 1


@pytest.mark.asyncio
async def test_delete_by_id(db_connection, file_record: FileRecord, user_id: int):
    """Test deleting a file by ID."""
    repo = FileRepository(db_connection)

    record_id = await repo.insert(file_record)

    # Delete the file
    success = await repo.delete_by_id(record_id, user_id)

    assert success is True

    # Verify deletion
    retrieved = await repo.get_by_id(record_id)
    assert retrieved is None


@pytest.mark.asyncio
async def test_delete_by_id_wrong_user(db_connection, file_record: FileRecord):
    """Test deleting a file by different user should fail."""
    repo = FileRepository(db_connection)

    record_id = await repo.insert(file_record)

    # Try to delete with different user_id
    success = await repo.delete_by_id(record_id, 999999)

    assert success is False

    # Verify file still exists
    retrieved = await repo.get_by_id(record_id)
    assert retrieved is not None


@pytest.mark.asyncio
async def test_total_file_count(db_connection, file_records: list[FileRecord]):
    """Test getting total file count."""
    repo = FileRepository(db_connection)

    count = await repo.total_file_count()

    assert count >= 2


@pytest.mark.asyncio
async def test_distinct_user_count(db_connection, file_records: list[FileRecord]):
    """Test getting distinct user count."""
    repo = FileRepository(db_connection)

    count = await repo.distinct_user_count()

    assert count >= 1
