# Test 4: Daily Reset Mechanism

**Date:** 2026-02-21
**Status:** ✅ PASSED

## Test Cases

### 4.1 Next Midnight Calculation
- **Function:** _get_next_midnight_utc()
- **Expected:** Returns datetime at 00:00:00 UTC tomorrow
- **Result:** ✅ PASS - Correctly calculates next midnight

### 4.2 Midnight Time Components
- **Expected:** hour=0, minute=0, second=0
- **Result:** ✅ PASS - All components are zero

### 4.3 Future Time Validation
- **Expected:** Next midnight is in the future
- **Result:** ✅ PASS - Within 24 hours from now

### 4.4 Reset Trigger Logic
- **Scenario:** quota_reset_time in the past
- **Expected:** Should trigger reset
- **Result:** ✅ PASS - datetime.now() >= past_reset_time

### 4.5 No Reset Logic
- **Scenario:** quota_reset_time in the future
- **Expected:** Should NOT trigger reset
- **Result:** ✅ PASS - datetime.now() < future_reset_time

## Code Verified
- `bot/database/repositories/quota_repo.py` lines 16-20, 164-196
- _get_next_midnight_utc() and check_and_reset_if_needed()
