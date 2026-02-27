# Storage Quota → Download Quota Migration

## TL;DR

> **Quick Summary**: Replace storage quota (upload tracking) with download quota (bandwidth + frequency tracking) with daily resets
> 
> **Deliverables**: Updated data model, quota logic, UI messages, and documentation
> - Updated `UserQuotaRecord` model with download tracking fields
> - Modified `quota_repo.py` with download quota enforcement
> - Updated handlers (`download.py`, `upload.py`, `admin.py`, `common.py`)
> - Enhanced `/mystats` command with download quota display
> - Updated configuration and documentation
> 
> **Estimated Effort**: Medium (structural changes across multiple files)
> **Parallel Execution**: YES - 3 waves (data model → logic → UI)
> **Critical Path**: Data model → Quota logic → Download handler → UI updates

---

## Context

### Original Request
Change "storage quota" to "download quota" in the Telegram bot project.

### Interview Summary
**Key Discussions**:
- User wants to track downloads instead of uploads
- Download quota should track BOTH bandwidth (bytes) AND frequency (count)
- Replace storage quota entirely - no dual system
- Keep 500MB default limit but track downloads
- Admins tracked but not enforced
- Reset all existing quota data to zero

**Research Findings**:
- Current quota tracks uploaded file sizes (`used_bytes`)
- Enforcement happens on upload (`upload.py:66`)
- Quota logic centralized in `quota_repo.py`
- Need daily reset mechanism (midnight UTC)

### Metis Review
**Identified Gaps** (addressed):
- **Download scope**: All download operations tracked (including `/claim`, share codes)
- **Concurrency**: Atomic quota operations to prevent race conditions
- **Token verification**: Required BEFORE download quota checks
- **Large files**: Block entirely if single file exceeds remaining quota

---

## Work Objectives

### Core Objective
Replace storage-based quota system with download-based quota system that tracks both bandwidth consumption and download frequency.

### Concrete Deliverables
- Updated `UserQuotaRecord` model with download tracking fields
- Modified `quota_repo.py` with download quota logic
- Updated download handler with quota enforcement
- Enhanced `/mystats` command with download quota display
- Updated admin commands for download quota management
- Updated documentation and configuration

### Definition of Done
- [x] All storage quota enforcement removed from upload operations
- [x] Download quota enforcement implemented for all download operations
- [x] `/mystats` shows both bandwidth and download count usage
- [x] Daily reset mechanism working correctly
- [x] All user-facing messages updated to "download quota" terminology

### Must Have
- Complete replacement of storage quota with download quota
- Daily reset at midnight UTC
- Both bandwidth and frequency tracking
- Admin exemption (tracked but not enforced)

### Must NOT Have (Guardrails)
- No dual quota systems (storage + download)
- No backward compatibility for storage quota data
- No complex rate limiting algorithms
- No analytics dashboards

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: NO (no existing test framework)
- **Automated tests**: NO (agent-executed QA scenarios only)
- **Agent-Executed QA**: ALWAYS (mandatory for all tasks)

### QA Policy
Every task MUST include agent-executed QA scenarios:
- **CLI/API**: Use Bash (curl) — Send requests, assert status + response fields
- **Evidence**: Save to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`

---

## Execution Strategy

### Parallel Execution Waves

> Target: 5-8 tasks per wave. Fewer than 3 per wave (except final) = under-splitting.

```
Wave 1 (Foundation — data model + configuration):
├── Task 1: Update UserQuotaRecord model [quick]
├── Task 2: Add download quota configuration [quick]
├── Task 3: Create quota reset mechanism [quick]
├── Task 4: Update quota repository interface [quick]
└── Task 5: Reset existing quota data [quick]

Wave 2 (Core Logic — quota enforcement):
├── Task 6: Implement download quota check [deep]
├── Task 7: Update download handler with quota enforcement [deep]
├── Task 8: Remove storage quota from upload handler [quick]
├── Task 9: Update file deletion logic [quick]
└── Task 10: Add admin download tracking [quick]

Wave 3 (User Interface — messages + commands):
├── Task 11: Update /mystats command [quick]
├── Task 12: Update admin commands [quick]
├── Task 13: Update help text and messages [writing]
├── Task 14: Update README documentation [writing]
└── Task 15: Test all download operations [unspecified-high]

Wave FINAL (Verification — independent review):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
```

---

## TODOs

> Implementation + Test = ONE Task. Every task MUST have: Recommended Agent Profile + QA Scenarios.

- [x] 1. Update UserQuotaRecord model

  **What to do**:
  - Add download tracking fields: `bandwidth_used`, `download_count`, `bandwidth_limit`, `download_limit`, `quota_reset_time`
  - Remove `used_bytes`, `quota_bytes`, `file_count` (storage tracking)
  - Add properties: `bandwidth_remaining`, `downloads_remaining`, `is_unlimited`
  - Update `to_mongo()` method for new fields

  **Must NOT do**:
  - Keep any storage quota tracking fields
  - Break existing token verification fields

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple data model changes with clear patterns
  - **Skills**: None needed for simple model updates

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2-5)
  - **Blocks**: Task 6 (quota repository logic)
  - **Blocked By**: None (can start immediately)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `bot/models/file_record.py:87-126` - Current UserQuotaRecord structure
  - `bot/models/file_record.py:106-120` - Property pattern (is_unlimited, remaining_bytes)

  **API/Type References** (contracts to implement against):
  - `bot/config.py:46` - default_quota_mb setting (reference for default limits)

  **WHY Each Reference Matters**:
  - Follow existing property pattern for consistency
  - Maintain same serialization approach with `to_mongo()`

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY — task is INCOMPLETE without these)**:

  ```
  Scenario: Model serialization preserves new fields
    Tool: Bash (python REPL)
    Preconditions: Updated UserQuotaRecord model
    Steps:
      1. Import UserQuotaRecord from bot.models.file_record
      2. Create instance with new download tracking fields
      3. Call to_mongo() method
      4. Assert all new fields are present in output
    Expected Result: All download tracking fields serialized correctly
    Evidence: .sisyphus/evidence/task-1-model-serialization.txt

  Scenario: Property calculations work correctly
    Tool: Bash (python REPL)
    Preconditions: Updated UserQuotaRecord model
    Steps:
      1. Create instance with bandwidth_used=750MB, bandwidth_limit=1GB
      2. Assert bandwidth_remaining property returns 250MB
      3. Create instance with download_count=32, download_limit=50
      4. Assert downloads_remaining property returns 18
    Expected Result: All property calculations return correct values
    Evidence: .sisyphus/evidence/task-1-properties.txt
  ```

  **Evidence to Capture**:
  - [ ] Each evidence file named: task-1-model-serialization.txt
  - [ ] task-1-properties.txt

  **Commit**: YES (groups with Tasks 2-5)
  - Message: `feat(quota): update UserQuotaRecord model for download tracking`
  - Files: `bot/models/file_record.py`

- [x] 2. Add download quota configuration

  **What to do**:
  - Add `default_bandwidth_limit_mb` and `default_download_limit` to Settings class
  - Add `quota_reset_timezone` setting (default: "UTC")
  - Update `.env.example` with new configuration variables
  - Update README.md configuration section

  **Must NOT do**:
  - Remove existing `default_quota_mb` setting (keep for backward compatibility)
  - Break existing configuration loading

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple configuration additions
  - **Skills**: None needed for config updates

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1,3-5)
  - **Blocks**: Task 6 (quota repository logic)
  - **Blocked By**: None (can start immediately)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `bot/config.py:46` - default_quota_mb setting pattern
  - `bot/config.py:1-80` - Settings class structure

  **Configuration References**:
  - `.env.example:14` - DEFAULT_QUOTA_MB configuration

  **WHY Each Reference Matters**:
  - Follow same configuration pattern for consistency
  - Maintain same environment variable naming convention

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY — task is INCOMPLETE without these)**:

  ```
  Scenario: Configuration loads correctly
    Tool: Bash (python REPL)
    Preconditions: Updated config.py
    Steps:
      1. Import Settings from bot.config
      2. Create instance with default values
      3. Assert new configuration fields exist with correct defaults
      4. Assert existing default_quota_mb still works
    Expected Result: All configuration fields accessible with correct defaults
    Evidence: .sisyphus/evidence/task-2-config-load.txt

  Scenario: Environment variables parsed correctly
    Tool: Bash (python REPL)
    Preconditions: Updated config.py
    Steps:
      1. Set environment variables for new configuration
      2. Create Settings instance
      3. Assert values loaded from environment correctly
    Expected Result: Environment variables override defaults correctly
    Evidence: .sisyphus/evidence/task-2-env-vars.txt
  ```

  **Evidence to Capture**:
  - [ ] task-2-config-load.txt
  - [ ] task-2-env-vars.txt

  **Commit**: YES (groups with Tasks 1,3-5)
  - Message: `feat(quota): add download quota configuration`
  - Files: `bot/config.py`, `.env.example`, `README.md`

- [x] 3. Create quota reset mechanism

  **What to do**:
  - Add `reset_daily_quota()` method to QuotaRepository
  - Implement logic to reset `bandwidth_used` and `download_count` at midnight UTC
  - Add check in `can_download()` to reset if `datetime.now() >= quota_reset_time`

  **Must NOT do**:
  - Implement complex timezone handling (stick to UTC)
  - Add manual reset triggers initially

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple date/time logic
  - **Skills**: None needed for datetime operations

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-2,4-5)
  - **Blocks**: Task 6 (quota repository logic)
  - **Blocked By**: None (can start immediately)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `bot/database/repositories/quota_repo.py:16-121` - Current repository methods
  - `bot/database/repositories/quota_repo.py:45-54` - Update pattern with datetime

  **External References**:
  - `datetime` module documentation for UTC handling

  **WHY Each Reference Matters**:
  - Follow same MongoDB update patterns
  - Use consistent UTC time handling

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY — task is INCOMPLETE without these)**:

  ```
  Scenario: Quota reset works correctly
    Tool: Bash (python REPL)
    Preconditions: Updated quota_repo.py
    Steps:
      1. Create user quota with bandwidth_used=900MB, download_count=45
      2. Set quota_reset_time to past datetime
      3. Call can_download() method
      4. Assert bandwidth_used and download_count reset to 0
    Expected Result: Quota counters reset when reset time reached
    Evidence: .sisyphus/evidence/task-3-reset-mechanism.txt

  Scenario: Reset time calculation correct
    Tool: Bash (python REPL)
    Preconditions: Updated quota_repo.py
    Steps:
      1. Test reset time calculation for different scenarios
      2. Verify next midnight UTC calculation
    Expected Result: Reset time always calculated correctly
    Evidence: .sisyphus/evidence/task-3-reset-time.txt
  ```

  **Evidence to Capture**:
  - [ ] task-3-reset-mechanism.txt
  - [ ] task-3-reset-time.txt

  **Commit**: YES (groups with Tasks 1-2,4-5)
  - Message: `feat(quota): add daily quota reset mechanism`
  - Files: `bot/database/repositories/quota_repo.py`

- [x] 4. Update quota repository interface

  **What to do**:
  - Add `can_download()` method to replace `can_upload()`
  - Add `add_download_usage()` method to replace `add_usage()`
  - Add `remove_download_usage()` method for file deletion
  - Update `set_quota()` to handle download limits

  **Must NOT do**:
  - Keep any upload quota methods
  - Break existing token verification methods

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Core logic changes requiring careful implementation
  - **Skills**: None needed for repository pattern

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-3,5)
  - **Blocks**: Task 7 (download handler enforcement)
  - **Blocked By**: Tasks 1-3 (depends on model and reset mechanism)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `bot/database/repositories/quota_repo.py:35-43` - can_upload method pattern
  - `bot/database/repositories/quota_repo.py:45-54` - add_usage method pattern

  **WHY Each Reference Matters**:
  - Follow same method signatures and patterns
  - Maintain consistent error handling and return types

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY — task is INCOMPLETE without these)**:

  ```
  Scenario: Download quota check works correctly
    Tool: Bash (python REPL)
    Preconditions: Updated quota_repo.py
    Steps:
      1. Create user with bandwidth_used=900MB, bandwidth_limit=1GB
      2. Test can_download() with 200MB file (should allow)
      3. Test can_download() with 300MB file (should block)
    Expected Result: Quota check correctly allows/denies downloads
    Evidence: .sisyphus/evidence/task-4-quota-check.txt

  Scenario: Usage tracking increments correctly
    Tool: Bash (python REPL)
    Preconditions: Updated quota_repo.py
    Steps:
      1. Create user with bandwidth_used=0, download_count=0
      2. Call add_download_usage() with 100MB file
      3. Assert bandwidth_used=100MB, download_count=1
    Expected Result: Usage counters increment correctly
    Evidence: .sisyphus/evidence/task-4-usage-tracking.txt
  ```

  **Evidence to Capture**:
  - [ ] task-4-quota-check.txt
  - [ ] task-4-usage-tracking.txt

  **Commit**: YES (groups with Tasks 1-3,5)
  - Message: `feat(quota): update quota repository interface for download tracking`
  - Files: `bot/database/repositories/quota_repo.py`

- [x] 5. Reset existing quota data

  **What to do**:
  - Create migration script to reset all `used_bytes` and `file_count` to 0
  - Set `bandwidth_used` and `download_count` to 0 for all users
  - Set `bandwidth_limit` and `download_limit` based on configuration defaults
  - Update `quota_reset_time` to next midnight UTC

  **Must NOT do**:
  - Delete any user quota records
  - Break token verification data

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple data migration script
  - **Skills**: None needed for MongoDB operations

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-4)
  - **Blocks**: Task 7 (download handler enforcement)
  - **Blocked By**: Tasks 1-4 (depends on updated model and interface)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `bot/database/connection.py:42-44` - MongoDB collection access pattern

  **WHY Each Reference Matters**:
  - Use same database connection patterns
  - Follow existing collection naming conventions

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY — task is INCOMPLETE without these)**:

  ```
  Scenario: Migration script runs successfully
    Tool: Bash (python script execution)
    Preconditions: Migration script created
    Steps:
      1. Run migration script
      2. Verify all user quotas have bandwidth_used=0, download_count=0
      3. Verify bandwidth_limit and download_limit set correctly
    Expected Result: All user data migrated to download quota system
    Evidence: .sisyphus/evidence/task-5-migration.txt

  Scenario: Token verification data preserved
    Tool: Bash (python REPL)
    Preconditions: Migration completed
    Steps:
      1. Check that download_token and token_verified_until fields unchanged
    Expected Result: Token verification data unaffected by migration
    Evidence: .sisyphus/evidence/task-5-tokens.txt
  ```

  **Evidence to Capture**:
  - [ ] task-5-migration.txt
  - [ ] task-5-tokens.txt

  **Commit**: YES (groups with Tasks 1-4)
  - Message: `feat(quota): migrate existing quota data to download tracking`
  - Files: `migration_script.py` (new file)

- [x] 6. Implement download quota check

  **What to do**:
  - Implement `can_download()` method with atomic check-and-increment
  - Check both bandwidth and frequency limits
  - Handle admin exemption (track but don't enforce)
  - Implement quota reset check before enforcement

  **Must NOT do**:
  - Allow race conditions in quota checking
  - Break existing token verification flow

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Critical logic requiring atomic operations
  - **Skills**: None needed for repository logic

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Tasks 1-5)
  - **Parallel Group**: Wave 2 (sequential within wave)
  - **Blocks**: Task 7 (download handler)
  - **Blocked By**: Tasks 1-5 (model, config, reset, interface, migration)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `bot/database/repositories/quota_repo.py:35-43` - can_upload atomic check pattern
  - `bot/config.py:27` - admin user ID checking pattern

  **WHY Each Reference Matters**:
  - Follow same atomic operation patterns
  - Maintain consistent admin exemption logic

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY — task is INCOMPLETE without these)**:

  ```
  Scenario: Atomic quota check prevents race conditions
    Tool: Bash (python REPL)
    Preconditions: Updated quota_repo.py
    Steps:
      1. Simulate concurrent download attempts
      2. Verify quota increments atomically
    Expected Result: No race conditions in quota tracking
    Evidence: .sisyphus/evidence/task-6-atomic-check.txt

  Scenario: Admin exemption works correctly
    Tool: Bash (python REPL)
    Preconditions: Updated quota_repo.py
    Steps:
      1. Test can_download() for admin user (should always allow)
      2. Test can_download() for regular user (should enforce limits)
    Expected Result: Admins bypass quota enforcement
    Evidence: .sisyphus/evidence/task-6-admin-exemption.txt
  ```

  **Evidence to Capture**:
  - [ ] task-6-atomic-check.txt
  - [ ] task-6-admin-exemption.txt

  **Commit**: YES (groups with Tasks 7-10)
  - Message: `feat(quota): implement atomic download quota check`
  - Files: `bot/database/repositories/quota_repo.py`

- [x] 7. Update download handler with quota enforcement

  **What to do**:
  - Add quota check in `_deliver_file()` method before file delivery
  - Update quota usage after successful file delivery
  - Add quota exceeded error messages
  - Handle quota reset timing correctly

  **Must NOT do**:
  - Break existing token verification
  - Allow downloads without quota checks

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Core handler logic changes
  - **Skills**: None needed for handler updates

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 6)
  - **Parallel Group**: Wave 2 (sequential within wave)
  - **Blocks**: Task 11 (mystats command)
  - **Blocked By**: Task 6 (quota check implementation)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `bot/handlers/download.py:50-80` - _deliver_file method structure
  - `bot/handlers/download.py:87-100` - Token verification pattern

  **WHY Each Reference Matters**:
  - Follow same error handling patterns
  - Maintain consistent user messaging approach

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY — task is INCOMPLETE without these)**:

  ```
  Scenario: Download quota enforced correctly
    Tool: Bash (curl API calls)
    Preconditions: Updated download.py
    Steps:
      1. Attempt download with exceeded quota
      2. Verify quota exceeded error message
      3. Attempt download within quota limits
      4. Verify successful download
    Expected Result: Quota enforcement working correctly
    Evidence: .sisyphus/evidence/task-7-quota-enforcement.txt

  Scenario: Quota usage increments after download
    Tool: Bash (curl API calls + database check)
    Preconditions: Updated download.py
    Steps:
      1. Check user quota before download
      2. Perform successful download
      3. Check user quota after download
      4. Verify bandwidth_used and download_count incremented
    Expected Result: Quota usage tracked correctly
    Evidence: .sisyphus/evidence/task-7-usage-tracking.txt
  ```

  **Evidence to Capture**:
  - [ ] task-7-quota-enforcement.txt
  - [ ] task-7-usage-tracking.txt

  **Commit**: YES (groups with Tasks 6,8-10)
  - Message: `feat(quota): add download quota enforcement to handler`
  - Files: `bot/handlers/download.py`

- [x] 8. Remove storage quota from upload handler

  **What to do**:
  - Remove `can_upload()` check from upload handler
  - Remove `add_usage()` call after successful upload
  - Update upload success message to remove quota references

  **Must NOT do**:
  - Break admin-only upload restriction
  - Remove duplicate file detection

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple removal of quota checks
  - **Skills**: None needed for handler updates

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 9-10)
  - **Blocks**: Task 15 (integration testing)
  - **Blocked By**: None (independent removal)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `bot/handlers/upload.py:64-82` - Current quota enforcement section

  **WHY Each Reference Matters**:
  - Remove exactly the quota-related code sections

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY — task is INCOMPLETE without these)**:

  ```
  Scenario: Uploads work without quota checks
    Tool: Bash (curl API calls)
    Preconditions: Updated upload.py
    Steps:
      1. Upload file as admin user
      2. Verify no quota-related messages appear
      3. Verify upload succeeds normally
    Expected Result: Uploads work without quota restrictions
    Evidence: .sisyphus/evidence/task-8-upload-no-quota.txt

  Scenario: Admin restriction still enforced
    Tool: Bash (curl API calls)
    Preconditions: Updated upload.py
    Steps:
      1. Attempt upload as non-admin user
      2. Verify admin-only restriction still works
    Expected Result: Admin-only upload restriction preserved
    Evidence: .sisyphus/evidence/task-8-admin-restriction.txt
  ```

  **Evidence to Capture**:
  - [ ] task-8-upload-no-quota.txt
  - [ ] task-8-admin-restriction.txt

  **Commit**: YES (groups with Tasks 6-7,9-10)
  - Message: `feat(quota): remove storage quota from upload handler`
  - Files: `bot/handlers/upload.py`

- [x] 9. Update file deletion logic

  **What to do**:
  - Update file deletion to use `remove_download_usage()` instead of `remove_usage()`
  - Ensure download quota decrements correctly

  **Must NOT do**:
  - Break file deletion functionality
  - Remove file record cleanup

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple method replacement
  - **Skills**: None needed for handler updates

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6-8,10)
  - **Blocks**: Task 15 (integration testing)
  - **Blocked By**: Task 4 (remove_download_usage method)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `bot/handlers/download.py:501` - Current file deletion quota removal

  **WHY Each Reference Matters**:
  - Replace exact quota removal call

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY — task is INCOMPLETE without these)**:

  ```
  Scenario: File deletion decrements download quota
    Tool: Bash (curl API calls + database check)
    Preconditions: Updated download.py
    Steps:
      1. Check user download quota before deletion
      2. Delete a file
      3. Check user download quota after deletion
      4. Verify download_count decremented
    Expected Result: File deletion correctly updates download quota
    Evidence: .sisyphus/evidence/task-9-deletion-quota.txt
  ```

  **Evidence to Capture**:
  - [ ] task-9-deletion-quota.txt

  **Commit**: YES (groups with Tasks 6-8,10)
  - Message: `feat(quota): update file deletion for download quota`
  - Files: `bot/handlers/download.py`

- [x] 10. Add admin download tracking

  **What to do**:
  - Ensure admin downloads are tracked in quota system
  - Verify admin exemption logic works correctly
  - Test that admin downloads don't trigger quota exceeded errors

  **Must NOT do**:
  - Break admin exemption
  - Allow admin tracking to affect quota enforcement

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple admin logic verification
  - **Skills**: None needed for admin handling

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6-9)
  - **Blocks**: Task 15 (integration testing)
  - **Blocked By**: Task 6 (admin exemption logic)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `bot/handlers/upload.py:27-29` - Admin checking pattern

  **WHY Each Reference Matters**:
  - Use consistent admin identification pattern

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY — task is INCOMPLETE without these)**:

  ```
  Scenario: Admin downloads tracked but not enforced
    Tool: Bash (curl API calls + database check)
    Preconditions: Updated quota system
    Steps:
      1. Perform multiple downloads as admin
      2. Verify quota tracking increments
      3. Verify no quota exceeded errors
    Expected Result: Admin downloads tracked but unlimited
    Evidence: .sisyphus/evidence/task-10-admin-tracking.txt
  ```

  **Evidence to Capture**:
  - [ ] task-10-admin-tracking.txt

  **Commit**: YES (groups with Tasks 6-9)
  - Message: `feat(quota): implement admin download tracking`
  - Files: `bot/database/repositories/quota_repo.py`, `bot/handlers/download.py`

- [x] 11. Update /mystats command

  **What to do**:
  - Update `/mystats` command to show download quota information
  - Display bandwidth usage, download count, and reset timer
  - Remove storage quota information

  **Must NOT do**:
  - Break existing token verification status display
  - Remove user identification information

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple command output formatting
  - **Skills**: None needed for message formatting

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 12-14)
  - **Blocks**: Task 15 (integration testing)
  - **Blocked By**: Tasks 1-10 (depends on quota system implementation)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `bot/handlers/download.py:522-543` - Current /mystats implementation

  **WHY Each Reference Matters**:
  - Follow same message formatting patterns

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY — task is INCOMPLETE without these)**:

  ```
  Scenario: /mystats shows download quota correctly
    Tool: Bash (curl API calls)
    Preconditions: Updated download.py
    Steps:
      1. Call /mystats command
      2. Verify download quota information displayed
      3. Verify storage quota information removed
    Expected Result: /mystats shows download quota correctly
    Evidence: .sisyphus/evidence/task-11-mystats.txt
  ```

  **Evidence to Capture**:
  - [ ] task-11-mystats.txt

  **Commit**: YES (groups with Tasks 12-14)
  - Message: `feat(quota): update /mystats for download quota`
  - Files: `bot/handlers/download.py`

- [x] 12. Update admin commands

  **What to do**:
  - Update `/setquota` command to handle download limits
  - Update admin dashboard to show download quota information
  - Add admin command to reset user download quotas

  **Must NOT do**:
  - Break existing admin functionality
  - Remove storage quota commands initially

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple command updates
  - **Skills**: None needed for admin commands

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 11,13-14)
  - **Blocks**: Task 15 (integration testing)
  - **Blocked By**: Tasks 1-10 (depends on quota system)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `bot/handlers/admin.py:65-90` - Current /setquota implementation

  **WHY Each Reference Matters**:
  - Follow same admin command patterns

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY — task is INCOMPLETE without these)**:

  ```
  Scenario: Admin commands work with download quota
    Tool: Bash (curl API calls)
    Preconditions: Updated admin.py
    Steps:
      1. Test /setquota with download limits
      2. Verify admin dashboard shows download info
    Expected Result: Admin commands handle download quota correctly
    Evidence: .sisyphus/evidence/task-12-admin-commands.txt
  ```

  **Evidence to Capture**:
  - [ ] task-12-admin-commands.txt

  **Commit**: YES (groups with Tasks 11,13-14)
  - Message: `feat(quota): update admin commands for download quota`
  - Files: `bot/handlers/admin.py`

- [x] 13. Update help text and messages

  **What to do**:
  - Update all user-facing messages from "storage quota" to "download quota"
  - Update help text in `common.py`
  - Update error messages for quota exceeded

  **Must NOT do**:
  - Break message formatting
  - Remove helpful information

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: Text content updates
  - **Skills**: None needed for message updates

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 11-12,14)
  - **Blocks**: Task 15 (integration testing)
  - **Blocked By**: Tasks 1-10 (depends on quota system)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `bot/handlers/common.py:34` - Current help text
  - `bot/handlers/upload.py:69` - Current quota exceeded message

  **WHY Each Reference Matters**:
  - Update exact message locations

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY — task is INCOMPLETE without these)**:

  ```
  Scenario: All messages updated correctly
    Tool: Bash (grep search)
    Preconditions: All files updated
    Steps:
      1. Search for "storage quota" in codebase
      2. Verify no instances remain
      3. Search for "download quota"
      4. Verify all relevant messages updated
    Expected Result: All terminology updated correctly
    Evidence: .sisyphus/evidence/task-13-message-updates.txt
  ```

  **Evidence to Capture**:
  - [ ] task-13-message-updates.txt

  **Commit**: YES (groups with Tasks 11-12,14)
  - Message: `feat(quota): update all messages to download quota terminology`
  - Files: `bot/handlers/common.py`, `bot/handlers/upload.py`, `bot/handlers/download.py`

- [x] 14. Update README documentation

  **What to do**:
  - Update README.md to describe download quota system
  - Update configuration documentation
  - Update usage examples

  **Must NOT do**:
  - Remove useful information
  - Break documentation structure

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: Documentation updates
  - **Skills**: None needed for documentation

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 11-13)
  - **Blocks**: Task 15 (integration testing)
  - **Blocked By**: Tasks 1-10 (depends on system implementation)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `README.md:8-15` - Current quota documentation

  **WHY Each Reference Matters**:
  - Update exact documentation sections

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY — task is INCOMPLETE without these)**:

  ```
  Scenario: Documentation updated correctly
    Tool: Bash (read file)
    Preconditions: Updated README.md
    Steps:
      1. Read README.md
      2. Verify download quota system described
      3. Verify storage quota references removed
    Expected Result: Documentation accurately reflects new system
    Evidence: .sisyphus/evidence/task-14-documentation.txt
  ```

  **Evidence to Capture**:
  - [ ] task-14-documentation.txt

  **Commit**: YES (groups with Tasks 11-13)
  - Message: `docs: update README for download quota system`
  - Files: `README.md`

- [x] 15. Test all download operations

  **What to do**:
  - Test `/get` command with various quota scenarios
  - Test `/claim` command with share codes
  - Test admin download exemption
  - Test quota reset mechanism

  **Must NOT do**:
  - Skip edge case testing
  - Assume functionality works without verification

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Comprehensive testing required
  - **Skills**: None needed for testing

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on all previous tasks)
  - **Parallel Group**: Wave 3 (sequential)
  - **Blocks**: Final verification tasks
  - **Blocked By**: Tasks 1-14 (all implementation tasks)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `bot/handlers/download.py:83-100` - /get command implementation

  **WHY Each Reference Matters**:
  - Test exact download operations

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY — task is INCOMPLETE without these)**:

  ```
  Scenario: Comprehensive download testing
    Tool: Bash (curl API calls + database checks)
    Preconditions: All implementation complete
    Steps:
      1. Test normal download within quota
      2. Test download exceeding quota
      3. Test admin download exemption
      4. Test quota reset after midnight
    Expected Result: All download scenarios work correctly
    Evidence: .sisyphus/evidence/task-15-comprehensive-testing.txt
  ```

  **Evidence to Capture**:
  - [ ] task-15-comprehensive-testing.txt

  **Commit**: YES (standalone)
  - Message: `test: comprehensive download quota testing`
  - Files: All modified files

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `python -m py_compile` on all changed files. Review all changed files for: empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp).
  Output: `Compile [PASS/FAIL] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (features working together, not isolation). Test edge cases: quota exceeded, admin exemption, daily reset. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Wave 1**: `feat(quota): foundation - data model and configuration` — Tasks 1-5
- **Wave 2**: `feat(quota): core logic - download quota enforcement` — Tasks 6-10
- **Wave 3**: `feat(quota): user interface - commands and messages` — Tasks 11-14
- **Wave 3**: `test(quota): comprehensive testing` — Task 15
- **Final**: `feat(quota): complete storage→download quota migration` — All files

---

## Success Criteria

### Verification Commands
```bash
# Test download quota enforcement
python run.py &
sleep 5
curl -X POST "http://localhost/..."
# Expected: Proper quota enforcement response
```

### Final Checklist
- [x] All storage quota enforcement removed
- [x] Download quota working for all operations
- [x] Daily reset mechanism functional
- [x] Admin exemption working correctly
- [x] All UI messages updated