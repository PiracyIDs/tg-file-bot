# Draft: Quota Migration Script

## Requirements (confirmed)
- Create migration script to reset all used_bytes and file_count to 0
- Add bandwidth tracking fields: bandwidth_used, download_count, bandwidth_limit, download_limit
- Set bandwidth_limit and download_limit based on configuration defaults
- Update quota_reset_time to next midnight UTC
- Preserve token verification data (download_token, token_verified_until)

## Technical Decisions
- Migration script will use existing MongoDB connection pattern from bot/database/connection.py
- Add new fields to UserQuotaRecord model
- Set default bandwidth_limit to same value as quota_bytes (storage quota)
- Set default download_limit to reasonable value (e.g., 100 downloads per day)
- Reset time: next midnight UTC

## Research Findings
- Current quota system tracks: used_bytes, quota_bytes, file_count, download_token, token_verified_until
- MongoDB collection: user_quotas
- Default quota: DEFAULT_QUOTA_MB=500 MB from .env
- No existing bandwidth tracking in current implementation

## Open Questions
- ~~What should be the default download_limit value?~~ RESOLVED: 100 downloads/day
- ~~Should bandwidth_limit be in MB like quota_bytes?~~ RESOLVED: Same as storage quota (DEFAULT_QUOTA_MB)
- ~~Any specific reset frequency preferences?~~ RESOLVED: Manual script - run once

## Technical Decisions Confirmed
- bandwidth_limit = DEFAULT_QUOTA_MB (500 MB) - same as storage quota
- download_limit = 100 downloads per day
- Migration script will be standalone manual script
- Reset time: next midnight UTC

## Scope Boundaries
- INCLUDE: Adding bandwidth tracking fields, resetting usage counters
- EXCLUDE: Modifying existing file storage logic, changing download verification system