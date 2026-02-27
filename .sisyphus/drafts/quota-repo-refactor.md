# Draft: Quota Repository Interface Update

## Requirements (confirmed)
- Replace upload quota system with download quota system
- Add `can_download()` method to replace `can_upload()`
- Add `add_download_usage()` method to replace `add_usage()`
- Add `remove_download_usage()` method for file deletion
- Update `set_quota()` to handle download limits
- Remove upload quota methods completely (clean break)

## Technical Decisions
- Keep existing token verification methods unchanged
- Update UserQuotaRecord model to track download-specific metrics
- Update all usage points in handlers to use new download methods
- **Migration Strategy**: Fresh start - reset all download tracking to zero
- **Quota Reset**: Daily reset - download quotas reset every 24 hours
- **Shared Files**: Yes, count all downloads against quota
- **Admin Privileges**: Yes, admins bypass all download quotas

## Research Findings
- Current quota tracking uses `used_bytes` and `file_count` fields
- `can_upload()` currently checks if `remaining_bytes >= file_size`
- `add_usage()` increments `used_bytes` and `file_count`
- `remove_usage()` decrements `used_bytes` and `file_count`
- Usage found in: upload.py, download.py, admin.py

## Scope Boundaries
- INCLUDE: All quota repository method replacements
- INCLUDE: Update all handler usage points
- INCLUDE: QA scenarios for download quota functionality
- EXCLUDE: Changes to token verification methods
- EXCLUDE: Database schema migration (tracking fields remain the same)

## Open Questions
- None - all requirements clarified

## Acceptance Criteria
- Download quota check works correctly
- Usage tracking increments correctly
- QA scenarios pass with agent-executed verification

## QA Scenarios Required
1. Create user with bandwidth_used=900MB, bandwidth_limit=1GB, test can_download() with 200MB file (should allow), test with 300MB file (should block)
2. Create user with bandwidth_used=0, download_count=0, call add_download_usage() with 100MB file, assert bandwidth_used=100MB, download_count=1