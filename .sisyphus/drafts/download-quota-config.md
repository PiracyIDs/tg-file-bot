# Draft: Download Quota Configuration Enhancement

## Requirements (confirmed)
- Add default_bandwidth_limit_mb and default_download_limit to Settings class
- Add quota_reset_timezone setting (default: "UTC")
- Update .env.example with new configuration variables
- Update README.md configuration section
- Keep existing default_quota_mb setting for backward compatibility
- Don't break existing configuration loading

## Technical Decisions
- **default_bandwidth_limit_mb**: Per-user bandwidth limit in MB (0 = unlimited)
- **default_download_limit**: Per-user concurrent download limit (0 = unlimited)
- **quota_reset_timezone**: Timezone for quota reset cycles (default: UTC)
- All new fields should have sensible defaults and proper validation

## Current Configuration Patterns
- Settings class uses Pydantic BaseSettings with environment variable loading
- Configuration section in README.md follows specific formatting
- .env.example uses consistent commenting style
- Quota-related settings are grouped together in config.py

## Research Findings
- Current quota system tracks storage quota only (default_quota_mb)
- No bandwidth or concurrent download limits currently implemented
- Settings validation uses Pydantic field_validator decorators
- Configuration is loaded lazily via singleton pattern

## Implementation Details

### Settings Class Additions (Questions Need Clarification)
- **default_bandwidth_limit_mb**: int = 1000 (1GB default bandwidth limit)
  - **Naming**: Should this be `default_bandwidth_quota_mb` to match existing `default_quota_mb`?
  - **Zero value**: Should 0 mean "unlimited" or "disabled"?
- **default_download_limit**: int = 10 
  - **Type**: Is this a count (max concurrent downloads) or size (like bandwidth)?
  - **Zero value**: Same semantic question as above
- **quota_reset_timezone**: str = "UTC" (Timezone for quota reset cycles)
  - **Validation**: Should invalid timezone strings cause error or default to UTC?

### Configuration Validation
- Add field validators for positive integers
- Ensure timezone validation using pytz or zoneinfo
- Maintain backward compatibility with existing settings

### Documentation Updates
- Add new configuration variables to .env.example
- Update README.md configuration section
- Include examples and explanations for new settings

## Acceptance Criteria
- Configuration loads correctly with new fields
- Environment variables parsed correctly
- Default values work as expected
- Existing functionality remains unchanged
- Documentation is comprehensive and clear

## Metis Review Findings
**Key questions needing clarification:**
1. **Naming consistency**: Existing uses `quota`, new uses `limit` - should they be consistent?
2. **Download limit type**: Is it a count or size?
3. **Zero value semantics**: Unlimited vs disabled
4. **Timezone validation**: Error vs fallback behavior

**Guardrails identified:**
- NO implementation logic changes
- NO database schema changes
- NO API/handler modifications
- Only configuration files affected