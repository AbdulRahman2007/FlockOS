# ADR 0006: Farm capacity and flock lifecycle

## Context

Phase 4 requires shed capacity enforcement, one active flock per shed, and closed flocks to remain locked until Owner or Super Admin reopens them. A placement total is an aggregate across placement facts and cannot be guarded by a normal row CHECK.

## Options

1. Validate only in the API, which can be bypassed by another DB client and races under concurrent placement requests.
2. Store a mutable placed-bird total on the shed and update it transactionally, creating a second source of truth.
3. Keep placements as facts and enforce the aggregate with PostgreSQL triggers that serialize writes on the shed row.

## Decision

Keep placement facts as the source of truth. Use a partial unique index for one active flock per shed, PostgreSQL triggers for aggregate capacity and closed-flock write protection, and matching pure/API validation for fast user feedback. A closed flock is the locked state; reopening requires Owner or Super Admin authorization and a reason in the audit entry. Super Admin looks up only the specified flock ID, derives its tenant from the row, receives status only, and the action records the reason.

Placed flocks cannot be hard-deleted. Users close a flock to lock it and retain its placement and activity history; the API rejects deletion with a conflict response.

## Consequences

Placement totals remain derivable and there is no mutable count to reconcile. PostgreSQL is required for full aggregate guarantees; SQLite unit tests alone cannot prove trigger behavior. The trigger integration test must run against migrated PostgreSQL in CI. The Super Admin reopen operation is a narrow exception to default tenant-data isolation and does not expose flock details.
