# Decisions - Storage to Download Quota Migration

## [2026-02-21] Session 6 - Architecture Decisions

### 1. Download Quota vs Storage Quota
- **Decision**: Complete replacement, not dual system
- **Rationale**: User requested tracking downloads, not uploads
- **Implementation**: All storage quota code removed

### 2. Quota Reset Timing
- **Decision**: Midnight UTC daily reset
- **Rationale**: Simple, predictable, no timezone complexity
- **Implementation**: `_get_next_midnight_utc()` helper

### 3. Admin Exemption
- **Decision**: Admins tracked but not enforced
- **Rationale**: Admins need unlimited access for management
- **Implementation**: `can_download()` returns `(True, quota, "admin_exempt")` for admins

### 4. File Deletion and Quota
- **Decision**: No quota refund on file deletion
- **Rationale**: Download quota tracks bandwidth consumed, not storage used
- **Implementation**: `remove_download_usage()` exists but not called in normal flow

### 5. Token Verification
- **Decision**: Non-admins must verify token before downloading
- **Rationale**: Security measure for non-admin users
- **Implementation**: 30-minute verification sessions

### 6. Backward Compatibility
- **Decision**: Keep `default_quota_mb` in config
- **Rationale**: Avoid breaking existing .env files
- **Implementation**: Field exists but not used in quota logic
