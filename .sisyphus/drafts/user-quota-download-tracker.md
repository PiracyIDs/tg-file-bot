# Draft: UserQuotaRecord - Storage to Download Tracking Conversion

## Current Implementation Analysis

**Current Model (Storage Quota):**
- `used_bytes: int = 0` - Running total of storage used
- `quota_bytes: int` - Storage limit (0 = unlimited)  
- `file_count: int = 0` - Number of files stored
- Properties: `is_unlimited`, `remaining_bytes`, `usage_percent`

**Current Repository Usage:**
- `quota_repo.py` has methods for storage tracking:
  - `add_usage(user_id, file_size)` - increments used_bytes + file_count
  - `remove_usage(user_id, file_size)` - decrements used_bytes + file_count
  - `can_upload(user_id, file_size)` - checks storage space remaining
  - `set_quota(user_id, quota_mb)` - sets storage limit

## Requirements for Download Tracking Conversion

### New Fields Needed:
- `bandwidth_used: int = 0` - Total bandwidth consumed in bytes
- `download_count: int = 0` - Total number of downloads
- `bandwidth_limit: int` - Bandwidth limit in bytes (0 = unlimited)
- `download_limit: int` - Maximum number of downloads allowed
- `quota_reset_time: Optional[datetime]` - When quotas reset

### Properties to Add:
- `bandwidth_remaining: int` - Remaining bandwidth
- `downloads_remaining: int` - Remaining downloads
- `is_unlimited: bool` - Check if unlimited (bandwidth_limit == 0)

### Fields to Preserve:
- `user_id: int`
- `download_token: Optional[str]`
- `token_verified_until: Optional[datetime]`
- `updated_at: datetime`

### Fields to Remove:
- `used_bytes: int`
- `quota_bytes: int` 
- `file_count: int`

## Impact Analysis

### Files Affected:
1. **bot/models/file_record.py** - Model definition update
2. **bot/database/repositories/quota_repo.py** - Repository methods update
3. **bot/handlers/admin.py** - Admin dashboard updates
4. **bot/handlers/upload.py** - Upload flow updates
5. **bot/handlers/download.py** - Download flow updates

### Repository Method Changes Needed:
- Replace `add_usage()` with `add_download_usage()`
- Replace `remove_usage()` with `remove_download_usage()`
- Replace `can_upload()` with `can_download()`
- Update `set_quota()` to handle bandwidth/download limits
- Update admin methods to show bandwidth/download stats

## User Decisions Confirmed

### Quota Reset Strategy
- **Daily reset** - Reset bandwidth/download counts every 24 hours

### Default Limits
- **Conservative limits**: 1GB bandwidth (1073741824 bytes), 50 downloads

### Backward Compatibility
- **Clean break** - Remove all storage tracking fields completely

## Updated Requirements

### Configuration Updates Needed:
- Add `DEFAULT_BANDWIDTH_MB: int = 1024` (1GB in MB)
- Add `DEFAULT_DOWNLOAD_LIMIT: int = 50`
- Add `QUOTA_RESET_INTERVAL: int = 86400` (24 hours in seconds)

### Model Migration Strategy:
- Complete removal of storage fields
- Add daily reset functionality using `quota_reset_time` field
- Update all repository methods to work with download tracking
- Update all UI/display logic to show bandwidth/download stats