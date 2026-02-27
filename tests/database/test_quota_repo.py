"""
Unit tests for QuotaRepository.
"""
import pytest
from datetime import datetime, timedelta, timezone

from bot.database.repositories.quota_repo import QuotaRepository, _get_next_midnight_utc
from bot.models.file_record import UserQuotaRecord


@pytest.mark.asyncio
async def test_get_quota_creates_new(db_connection, user_id: int):
    """Test that get creates a new quota record if it doesn't exist."""
    repo = QuotaRepository(db_connection)

    quota = await repo.get(user_id)

    assert quota is not None
    assert quota.user_id == user_id
    assert quota.bandwidth_limit == 500 * 1024 * 1024  # Default 500 MB
    assert quota.bandwidth_used == 0
    assert quota.download_count == 0


@pytest.mark.asyncio
async def test_get_quota_existing(db_connection, user_id: int, user_quota_record: UserQuotaRecord):
    """Test that get returns existing quota record."""
    repo = QuotaRepository(db_connection)

    # Insert a custom quota
    await db_connection["user_quotas"].insert_one(user_quota_record.to_mongo())

    # Get the quota
    quota = await repo.get(user_id)

    assert quota.user_id == user_id
    assert quota.bandwidth_limit == user_quota_record.bandwidth_limit
    assert quota.bandwidth_used == user_quota_record.bandwidth_used


@pytest.mark.asyncio
async def test_can_download_unlimited(db_connection, user_id: int):
    """Test that unlimited users can always download."""
    repo = QuotaRepository(db_connection)

    # Set unlimited quota
    await repo.set_quota(user_id, bandwidth_mb=0, download_limit=0)

    # Check if can download (10 MB file)
    file_size = 10 * 1024 * 1024
    allowed, quota, reason = await repo.can_download(user_id, file_size, is_admin=False)

    assert allowed is True
    assert reason == "ok"


@pytest.mark.asyncio
async def test_can_download_bandwidth_enough(db_connection, user_id: int):
    """Test that download is allowed when there's enough bandwidth."""
    repo = QuotaRepository(db_connection)

    # Set a quota with 100 MB limit
    await repo.set_quota(user_id, bandwidth_mb=100, download_limit=10)

    # Use 10 MB
    await repo.add_download_usage(user_id, 10 * 1024 * 1024)

    # Try to download a 5 MB file
    file_size = 5 * 1024 * 1024
    allowed, quota, reason = await repo.can_download(user_id, file_size, is_admin=False)

    assert allowed is True
    assert reason == "ok"
    assert quota.bandwidth_remaining == (100 - 10 - 5) * 1024 * 1024


@pytest.mark.asyncio
async def test_can_download_bandwidth_exceeded(db_connection, user_id: int):
    """Test that download is denied when bandwidth is exceeded."""
    repo = QuotaRepository(db_connection)

    # Set a quota with 100 MB limit
    await repo.set_quota(user_id, bandwidth_mb=100, download_limit=10)

    # Use 99 MB
    await repo.add_download_usage(user_id, 99 * 1024 * 1024)

    # Try to download a 5 MB file (would exceed limit)
    file_size = 5 * 1024 * 1024
    allowed, quota, reason = await repo.can_download(user_id, file_size, is_admin=False)

    assert allowed is False
    assert reason == "bandwidth_exceeded"


@pytest.mark.asyncio
async def test_can_download_count_exceeded(db_connection, user_id: int):
    """Test that download is denied when daily count is exceeded."""
    repo = QuotaRepository(db_connection)

    # Set a quota with 2 downloads per day
    await repo.set_quota(user_id, bandwidth_mb=100, download_limit=2)

    # Use 1 download
    await repo.add_download_usage(user_id, 1024)  # Small file

    # Try to download again (should be allowed, as we have 1 left)
    allowed, quota, _ = await repo.can_download(user_id, 1024, is_admin=False)
    assert allowed is True

    # Use another download (now at 2/2)
    await repo.add_download_usage(user_id, 1024)

    # Try to download again (should be denied)
    allowed, quota, reason = await repo.can_download(user_id, 1024, is_admin=False)

    assert allowed is False
    assert reason == "download_count_exceeded"


@pytest.mark.asyncio
async def test_can_download_admin_bypass(db_connection, user_id: int):
    """Test that admins bypass quota enforcement."""
    repo = QuotaRepository(db_connection)

    # Set a very low quota
    await repo.set_quota(user_id, bandwidth_mb=1, download_limit=1)

    # Use all quota
    await repo.add_download_usage(user_id, 2 * 1024 * 1024)  # 2 MB

    # Admin should still be able to download
    file_size = 10 * 1024 * 1024  # 10 MB
    allowed, quota, reason = await repo.can_download(user_id, file_size, is_admin=True)

    assert allowed is True
    assert reason == "admin_exempt"


@pytest.mark.asyncio
async def test_add_download_usage(db_connection, user_id: int):
    """Test adding download usage."""
    repo = QuotaRepository(db_connection)

    # Add 10 MB download
    await repo.add_download_usage(user_id, 10 * 1024 * 1024)

    quota = await repo.get(user_id)
    assert quota.bandwidth_used == 10 * 1024 * 1024
    assert quota.download_count == 1

    # Add another 5 MB
    await repo.add_download_usage(user_id, 5 * 1024 * 1024)

    quota = await repo.get(user_id)
    assert quota.bandwidth_used == 15 * 1024 * 1024
    assert quota.download_count == 2


@pytest.mark.asyncio
async def test_remove_download_usage(db_connection, user_id: int):
    """Test removing download usage."""
    repo = QuotaRepository(db_connection)

    # Add 10 MB download
    await repo.add_download_usage(user_id, 10 * 1024 * 1024)

    # Remove 5 MB
    await repo.remove_download_usage(user_id, 5 * 1024 * 1024)

    quota = await repo.get(user_id)
    assert quota.bandwidth_used == 5 * 1024 * 1024
    assert quota.download_count == 1

    # Remove more than available (should floor at 0)
    await repo.remove_download_usage(user_id, 10 * 1024 * 1024)

    quota = await repo.get(user_id)
    assert quota.bandwidth_used == 0
    assert quota.download_count == 0


@pytest.mark.asyncio
async def test_set_quota(db_connection, user_id: int):
    """Test setting quota limits."""
    repo = QuotaRepository(db_connection)

    # Set custom quota
    await repo.set_quota(user_id, bandwidth_mb=200, download_limit=5)

    quota = await repo.get(user_id)
    assert quota.bandwidth_limit == 200 * 1024 * 1024
    assert quota.download_limit == 5


@pytest.mark.asyncio
async def test_set_quota_unlimited(db_connection, user_id: int):
    """Test setting unlimited quota."""
    repo = QuotaRepository(db_connection)

    # Set unlimited
    await repo.set_quota(user_id, bandwidth_mb=0, download_limit=0)

    quota = await repo.get(user_id)
    assert quota.bandwidth_limit == 0
    assert quota.download_limit == 0
    assert quota.is_unlimited is True


@pytest.mark.asyncio
async def test_all_quotas(db_connection, user_id: int):
    """Test getting all quotas."""
    repo = QuotaRepository(db_connection)

    # Create quotas for multiple users
    await repo.set_quota(user_id, bandwidth_mb=100, download_limit=10)
    await repo.set_quota(user_id + 1, bandwidth_mb=200, download_limit=20)

    # Get all quotas
    quotas = await repo.all_quotas()

    assert len(quotas) >= 2


@pytest.mark.asyncio
async def test_get_verify_status(db_connection, user_id: int):
    """Test getting verification status."""
    repo = QuotaRepository(db_connection)

    # Get status for new user
    status = await repo.get_verify_status(user_id)

    assert status["is_verified"] is False
    assert status["verify_token"] is None
    assert status["verified_time"] is None
    assert status["verify_count"] == 0

    # Update verification status
    await repo.update_verify_status(user_id, is_verified=True, verify_token="test_token")

    # Get updated status
    status = await repo.get_verify_status(user_id)

    assert status["is_verified"] is True
    assert status["verify_token"] == "test_token"
    assert status["verified_time"] is not None


@pytest.mark.asyncio
async def test_update_verify_status(db_connection, user_id: int):
    """Test updating verification status."""
    repo = QuotaRepository(db_connection)

    # Set verified
    now = datetime.now(timezone.utc)
    await repo.update_verify_status(user_id, is_verified=True, verify_token="token123")

    status = await repo.get_verify_status(user_id)
    assert status["is_verified"] is True
    assert status["verify_token"] == "token123"
    assert (status["verified_time"] - now).total_seconds() < 1

    # Set unverified
    await repo.update_verify_status(user_id, is_verified=False)

    status = await repo.get_verify_status(user_id)
    assert status["is_verified"] is False


@pytest.mark.asyncio
async def test_reset_daily_quota(db_connection, user_id: int):
    """Test resetting daily quota."""
    repo = QuotaRepository(db_connection)

    # Set a quota and use some bandwidth
    await repo.set_quota(user_id, bandwidth_mb=100, download_limit=10)
    await repo.add_download_usage(user_id, 50 * 1024 * 1024)

    quota = await repo.get(user_id)
    assert quota.bandwidth_used == 50 * 1024 * 1024

    # Reset quota
    await repo.reset_daily_quota(user_id)

    quota = await repo.get(user_id)
    assert quota.bandwidth_used == 0
    assert quota.download_count == 0

    # Verify quota limits are still set
    assert quota.bandwidth_limit == 100 * 1024 * 1024
    assert quota.download_limit == 10


@pytest.mark.asyncio
async def test_check_and_reset_if_needed(db_connection, user_id: int):
    """Test automatic quota reset when reset time has passed."""
    repo = QuotaRepository(db_connection)

    # Set quota with reset time in the past
    await repo.set_quota(user_id, bandwidth_mb=100, download_limit=10)
    await repo.add_download_usage(user_id, 50 * 1024 * 1024)

    # Manually set quota_reset_time to the past
    past_time = datetime.now(timezone.utc) - timedelta(hours=1)
    await repo.col.update_one(
        {"user_id": user_id},
        {"$set": {"quota_reset_time": past_time}}
    )

    # Check if reset is needed
    was_reset = await repo.check_and_reset_if_needed(user_id)

    assert was_reset is True

    quota = await repo.get(user_id)
    assert quota.bandwidth_used == 0
    assert quota.download_count == 0


def test_get_next_midnight_utc():
    """Test that next midnight is correctly calculated."""
    midnight = _get_next_midnight_utc()

    # Should be in the future
    assert midnight > datetime.now(timezone.utc)

    # Should have time component 00:00:00
    assert midnight.hour == 0
    assert midnight.minute == 0
    assert midnight.second == 0
    assert midnight.microsecond == 0

    # Should be tomorrow
    tomorrow = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    assert midnight == tomorrow
