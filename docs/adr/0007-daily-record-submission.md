# ADR-0007: Daily record submission and edit workflow

## Context

Daily facts are tenant-scoped, unique per flock and farm-local date, and must survive retries without creating duplicate rows. Bird counts are derived from placement and daily facts. Edits need optimistic conflict detection, role windows, and an audit trail. V1 keeps drafts locally but remains online-only.

## Options

1. Mutable daily totals updated in place without replay protection.
2. One daily fact row per flock/date, idempotency key and request hash on submission, versioned edits, and derived counts recalculated through the domain ledger inside the write transaction.

## Decision

Use option 2. A database unique constraint enforces `(tenant_id, flock_id, record_date)`. A second constraint scopes idempotency keys to tenant and submitting user; replays with the same request hash return the existing record, while key reuse with different data conflicts. Edits require the current version, lock the flock and record for the transaction, recompute from the changed date, reject invalid closing bird counts, and append before/after audit values. No aggregate count is stored.

Daily records use the farm's configured IANA time zone for date windows. Owner edits have no past-date limit. The tenant Owner configures Manager and Worker windows from 1 to 30 calendar dates (inclusive of today), defaulting to seven and one day respectively. Workers may edit only their own records. Future daily records are rejected. Weight samples are unique per flock/date and must be at least seven days apart. Bag purchases store entered quantity, unit, configured bag-size snapshot, and normalized kilograms.

The mobile form preselects flock/date when opened from a flock, defaults deaths/culling to zero and carries forward feed/water/temperature from the latest record where available. Drafts and their idempotency key are saved in browser local storage. Failed creates retry with the same key. The normal-flow tap target is six actions: focus and enter the five required numeric fields, then submit; flock and date are preselected, notes are optional.

## Consequences

- Retries cannot duplicate a daily record; updates reject stale versions with a conflict response.
- Daily totals remain derived and reproducible; a backdated change validates the full affected suffix before commit.
- Local drafts support recovery after request failure, but not offline synchronization or cross-device recovery.
- The six-action target assumes a preselected active flock and date; choosing another flock/date adds an action.
- The 1–30-day configuration limit, weekly-sample spacing, future-date, and prefill rules are explicit Phase 6 implementation assumptions and can be revised by a later owner decision.
