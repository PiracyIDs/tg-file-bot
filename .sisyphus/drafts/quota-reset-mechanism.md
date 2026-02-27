# Draft: Quota Reset Mechanism

## Requirements (confirmed)
- Add `reset_daily_quota()` method to QuotaRepository
- Implement logic to reset `bandwidth_used` and `download_count` at midnight UTC
- Add check in `can_download()` to reset if `datetime.now() >= quota_reset_time`

## Technical Decisions
- Use UTC timezone only (no complex timezone handling)
- Store `quota_reset_time` field in UserQuotaRecord
- Reset mechanism triggers automatically during download checks
- No manual reset triggers initially

## Research Findings
- Current quota system tracks storage usage (upload-based) only
- No existing bandwidth tracking or download counting
- UserQuotaRecord currently has: `used_bytes`, `quota_bytes`, `file_count`, `download_token`, `token_verified_until`
- Need to add: `bandwidth_used`, `download_count`, `quota_reset_time`

## Technical Decisions
- Use UTC timezone only (no complex timezone handling)
- Store `quota_reset_time` field in UserQuotaRecord
- Reset mechanism triggers automatically during download checks
- No manual reset triggers initially
- **Block downloads entirely** when quota exceeded
- Track **both download count and bandwidth usage**
- Use **same default quota as storage** (DEFAULT_QUOTA_MB)
- **Admins bypass all quotas** (consistent with storage behavior)
- **Separate download quota** with new fields: `quota_download_count`, `quota_bandwidth_mb`

## Research Findings
- Current quota system tracks storage usage (upload-based) only
- No existing bandwidth tracking or download counting
- UserQuotaRecord currently has: `used_bytes`, `quota_bytes`, `file_count`, `download_token`, `token_verified_until`
- Need to add: `bandwidth_used`, `download_count`, `quota_reset_time`, `quota_download_count`, `quota_bandwidth_mb`

## Scope Boundaries
- INCLUDE: Automatic daily reset mechanism
- INCLUDE: Download bandwidth tracking
- INCLUDE: Download count tracking
- EXCLUDE: Complex timezone handling
- EXCLUDE: Manual reset triggers initially