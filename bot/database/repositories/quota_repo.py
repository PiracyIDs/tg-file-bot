"""
Repository: per-user download quota tracking.
Collection: 'user_quotas'
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from bot.config import settings
from bot.models.file_record import UserQuotaRecord

logger = logging.getLogger(__name__)
COL = "user_quotas"


def _get_next_midnight_utc() -> datetime:
    """Calculate next midnight UTC."""
    now = datetime.now(timezone.utc)
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return tomorrow


class QuotaRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db[COL]

    async def _get_or_create(self, user_id: int) -> UserQuotaRecord:
        doc = await self.col.find_one({"user_id": user_id})
        if doc:
            return UserQuotaRecord(**doc)
        # First time — create with default download quota from config
        new = UserQuotaRecord(
            user_id=user_id,
            bandwidth_limit=settings.default_bandwidth_limit_mb * 1024 * 1024,
            download_limit=settings.default_download_limit,
            quota_reset_time=_get_next_midnight_utc(),
        )
        await self.col.insert_one(new.to_mongo())
        return new

    async def get(self, user_id: int) -> UserQuotaRecord:
        return await self._get_or_create(user_id)

    async def can_download(
        self, user_id: int, file_size: int, is_admin: bool = False
    ) -> tuple[bool, UserQuotaRecord, str]:
        """
        Check if user can download a file of given size.
        
        Returns (allowed, quota_record, reason).
        - Admins are always allowed (tracked but not enforced)
        - Checks both bandwidth and download count limits
        - Automatically resets quota if reset_time has passed
        """
        # Check and reset if needed
        await self.check_and_reset_if_needed(user_id)
        
        quota = await self._get_or_create(user_id)
        
        # Admins bypass enforcement
        if is_admin:
            return True, quota, "admin_exempt"
        
        # Check bandwidth limit
        if not quota.is_unlimited and quota.bandwidth_remaining < file_size:
            return False, quota, "bandwidth_exceeded"
        
        # Check download count limit
        if quota.download_limit > 0 and quota.downloads_remaining <= 0:
            return False, quota, "download_count_exceeded"
        
        return True, quota, "ok"

    async def add_download_usage(self, user_id: int, file_size: int) -> None:
        """Increment bandwidth_used and download_count atomically."""
        await self.col.update_one(
            {"user_id": user_id},
            {
                "$inc": {"bandwidth_used": file_size, "download_count": 1},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
            upsert=True,
        )

    async def remove_download_usage(self, user_id: int, file_size: int) -> None:
        """
        Decrement bandwidth_used and download_count (floor at 0).
        Note: Typically not used for downloads, but provided for admin corrections.
        """
        quota = await self._get_or_create(user_id)
        new_bandwidth = max(0, quota.bandwidth_used - file_size)
        new_count = max(0, quota.download_count - 1)
        await self.col.update_one(
            {"user_id": user_id},
            {"$set": {
                "bandwidth_used": new_bandwidth,
                "download_count": new_count,
                "updated_at": datetime.now(timezone.utc),
            }},
        )

    async def set_quota(
        self, user_id: int, bandwidth_mb: int, download_limit: int = 0
    ) -> None:
        """
        Admin: set download quota limits.
        
        Args:
            user_id: User to update
            bandwidth_mb: Daily bandwidth limit in MB (0 = unlimited)
            download_limit: Daily download count limit (0 = unlimited)
        """
        await self.col.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "bandwidth_limit": bandwidth_mb * 1024 * 1024,
                    "download_limit": download_limit,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

    async def all_quotas(self) -> list[UserQuotaRecord]:
        """Admin: list all user quota records sorted by bandwidth usage."""
        cursor = self.col.find({}).sort("bandwidth_used", -1)
        return [UserQuotaRecord(**d) for d in await cursor.to_list(500)]

    async def set_download_token(self, user_id: int, token: str) -> None:
        """Set user's download verification token."""
        await self.col.update_one(
            {"user_id": user_id},
            {"$set": {"download_token": token, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

    async def get_download_token(self, user_id: int) -> Optional[str]:
        """Get user's download verification token."""
        doc = await self.col.find_one({"user_id": user_id})
        return doc.get("download_token") if doc else None

    async def set_token_verified(self, user_id: int, until: datetime) -> None:
        """Mark user's token as verified until given datetime."""
        await self.col.update_one(
            {"user_id": user_id},
            {"$set": {"token_verified_until": until, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

    async def is_token_verified(self, user_id: int) -> bool:
        """Check if user's token is currently verified (old method - deprecated)."""
        doc = await self.col.find_one({"user_id": user_id})
        if not doc:
            return False
        verified_until = doc.get("token_verified_until")
        if not verified_until:
            return False
        # Ensure both datetimes are timezone-aware for comparison
        if verified_until.tzinfo is None:
            verified_until = verified_until.replace(tzinfo=timezone.utc)
        return verified_until > datetime.now(timezone.utc)

    # ── Shortlink Token Verification Methods ───────────────────────────────────

    async def get_verify_status(self, user_id: int) -> dict:
        """Get user's verification status.
        
        Returns dict with:
        - is_verified: bool
        - verify_token: str
        - verified_time: datetime or None
        - verify_count: int
        """
        doc = await self.col.find_one({"user_id": user_id})
        if not doc:
            return {
                "is_verified": False,
                "verify_token": None,
                "verified_time": None,
                "verify_count": 0,
            }
        return {
            "is_verified": doc.get("is_verified", False),
            "verify_token": doc.get("verify_token"),
            "verified_time": doc.get("verified_time"),
            "verify_count": doc.get("verify_count", 0),
        }

    async def update_verify_status(
        self, user_id: int, is_verified: bool = None, verify_token: str = None
    ) -> None:
        """Update user's verification status."""
        update_data = {"updated_at": datetime.now(timezone.utc)}
        if is_verified is not None:
            update_data["is_verified"] = is_verified
            if is_verified:
                update_data["verified_time"] = datetime.now(timezone.utc)
        if verify_token is not None:
            update_data["verify_token"] = verify_token

        await self.col.update_one(
            {"user_id": user_id},
            {"$set": update_data},
            upsert=True,
        )

    async def get_verify_count(self, user_id: int) -> int:
        """Get user's verification count."""
        doc = await self.col.find_one({"user_id": user_id})
        return doc.get("verify_count", 0) if doc else 0

    async def set_verify_count(self, user_id: int, count: int) -> None:
        """Set user's verification count."""
        await self.col.update_one(
            {"user_id": user_id},
            {"$set": {"verify_count": count, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

    async def get_total_verify_count(self) -> int:
        """Get total verification count across all users (for admin stats)."""
        pipeline = [
            {"$group": {"_id": None, "total": {"$sum": "$verify_count"}}}
        ]
        result = await self.col.aggregate(pipeline).to_list(1)
        return result[0]["total"] if result else 0

    async def reset_all_verify_counts(self) -> None:
        """Reset verify_count to 0 for all users."""
        await self.col.update_many(
            {},
            {"$set": {"verify_count": 0, "updated_at": datetime.now(timezone.utc)}},
        )

    async def reset_daily_quota(self, user_id: int) -> None:
        """Reset daily quota counters (bandwidth_used, download_count)."""
        await self.col.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "bandwidth_used": 0,
                    "download_count": 0,
                    "quota_reset_time": _get_next_midnight_utc(),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

    async def check_and_reset_if_needed(self, user_id: int) -> bool:
        """
        Check if quota needs reset and reset if reset time has passed.
        
        Returns True if a reset was performed.
        """
        quota = await self._get_or_create(user_id)
        
        # If no reset time set, initialize it
        if not quota.quota_reset_time:
            await self.reset_daily_quota(user_id)
            return True
            
        # Ensure both datetimes are timezone-aware for comparison
        reset_time = quota.quota_reset_time
        if reset_time.tzinfo is None:
            reset_time = reset_time.replace(tzinfo=timezone.utc)
        # Check if reset time has passed
        if datetime.now(timezone.utc) >= reset_time:
            await self.reset_daily_quota(user_id)
            return True
            
        return False
