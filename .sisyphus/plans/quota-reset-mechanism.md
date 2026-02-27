# Quota Reset Mechanism Implementation

## TL;DR

> **Quick Summary**: Add daily quota reset functionality to track download bandwidth and count, resetting at midnight UTC
> 
> **Deliverables**: Modified UserQuotaRecord model, new QuotaRepository methods, updated download flow with quota checks
> - Updated `bot/models/file_record.py` - Add quota tracking fields
> - Updated `bot/database/repositories/quota_repo.py` - Add reset logic and quota checks
> - Updated `bot/handlers/download.py` - Integrate quota checks into download flow
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Model update → Repository logic → Download integration

---

## Context

### Original Request
Create quota reset mechanism in bot/database/repositories/quota_repo.py

### Interview Summary
**Key Discussions**:
- Block downloads entirely when quota exceeded
- Track both download count and bandwidth usage  
- Use same default quota as storage (DEFAULT_QUOTA_MB)
- Admins bypass all quotas (consistent with storage behavior)
- Separate download quota with new fields: quota_download_count, quota_bandwidth_mb

**Research Findings**:
- Current quota system tracks storage usage (upload-based) only
- No existing bandwidth tracking or download counting
- UserQuotaRecord needs new fields: bandwidth_used, download_count, quota_reset_time, quota_download_count, quota_bandwidth_mb

### Metis Review
**Identified Gaps** (addressed):
- Clarified quota enforcement behavior (block vs warn vs throttle)
- Confirmed admin bypass behavior consistency
- Added explicit scope boundaries to prevent creep
- Defined atomic reset requirements

---

## Work Objectives

### Core Objective
Implement automatic daily quota reset for download tracking, integrating seamlessly with existing storage quota system

### Concrete Deliverables
- Modified UserQuotaRecord model with download tracking fields
- reset_daily_quota() method in QuotaRepository
- can_download() method with automatic reset logic
- Updated download handlers with quota checks

### Definition of Done
- [ ] All new fields added to UserQuotaRecord
- [ ] reset_daily_quota() method implemented
- [ ] can_download() method with reset logic implemented
- [ ] Download flow integrates quota checks
- [ ] Admin bypass works correctly
- [ ] QA scenarios pass with evidence captured

### Must Have
- Automatic reset at midnight UTC
- Download bandwidth and count tracking
- Block downloads when quota exceeded
- Admin bypass functionality

### Must NOT Have (Guardrails)
- Complex timezone handling (UTC only)
- Manual reset triggers initially
- Bandwidth throttling mechanisms
- Notification systems for quota warnings

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.
> Acceptance criteria requiring "user manually tests/confirms" are FORBIDDEN.

### Test Decision
- **Infrastructure exists**: YES (bun test)
- **Automated tests**: YES (TDD)
- **Framework**: bun test
- **If TDD**: Each task follows RED (failing test) → GREEN (minimal impl) → REFACTOR

### QA Policy
Every task MUST include agent-executed QA scenarios (see TODO template below).
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Frontend/UI**: Use Playwright (playwright skill) — Navigate, interact, assert DOM, screenshot
- **TUI/CLI**: Use interactive_bash (tmux) — Run command, send keystrokes, validate output
- **API/Backend**: Use Bash (curl) — Send requests, assert status + response fields
- **Library/Module**: Use Bash (bun/node REPL) — Import, call functions, compare output

---

## Execution Strategy

### Parallel Execution Waves

> Maximize throughput by grouping independent tasks into parallel waves.
> Each wave completes before the next begins.
> Target: 5-8 tasks per wave. Fewer than 3 per wave (except final) = under-splitting.

```
Wave 1 (Start Immediately — model updates + config):
├── Task 1: Update UserQuotaRecord model [quick]
├── Task 2: Add config for download quota [quick]
├── Task 3: Update QuotaRepository constructor [quick]
└── Task 4: Create test file structure [quick]

Wave 2 (After Wave 1 — core quota logic):
├── Task 5: Implement reset_daily_quota() method [deep]
├── Task 6: Implement can_download() method [deep]
├── Task 7: Add quota usage tracking methods [unspecified-high]
└── Task 8: Create comprehensive tests [unspecified-high]

Wave 3 (After Wave 2 — download integration):
├── Task 9: Integrate quota checks into download flow [deep]
├── Task 10: Update admin bypass logic [quick]
└── Task 11: End-to-end testing [unspecified-high]

Wave FINAL (After ALL tasks — independent review):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
└── Task F3: Real manual QA (unspecified-high)

Critical Path: Task 1 → Task 5 → Task 6 → Task 9 → F1-F3
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 4 (Wave 1)
```

### Dependency Matrix (abbreviated — show ALL tasks in your generated plan)

- **1-4**: — — 5-8, 1
- **5**: 1, 3 — 6, 7, 2
- **6**: 1, 3 — 9, 2
- **7**: 1, 3 — 9, 2
- **9**: 5, 6, 7 — 10, 11, 3

> This is abbreviated for reference. YOUR generated plan must include the FULL matrix for ALL tasks.

### Agent Dispatch Summary

- **1**: **4** — T1-T3 → `quick`, T4 → `quick`
- **2**: **4** — T5-T6 → `deep`, T7 → `unspecified-high`, T8 → `unspecified-high`
- **3**: **3** — T9 → `deep`, T10 → `quick`, T11 → `unspecified-high`
- **FINAL**: **3** — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.
> **A task WITHOUT QA Scenarios is INCOMPLETE. No exceptions.**