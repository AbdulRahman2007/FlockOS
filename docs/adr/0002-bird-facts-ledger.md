# ADR 0002: Bird-count facts and derived ledger

- Status: Proposed for review
- Date: 2026-10-12

## Context

Bird totals must never be hand-edited. D2 defines remaining birds from placement, mortality, culling, sales, and transfers. Daily records are unique per flock/local date, gaps are flags rather than zero rows, and edits recompute from the changed date. Closed flocks reject changes except Owner/Super Admin reopen with reason. Negative closing counts are rejected.

## Options

1. Store mutable current/remaining counts on flock rows and update them during each operation.
2. Store business facts and calculate totals when needed; optionally persist rebuildable read projections.
3. Store a single generic immutable event stream for every operational fact.

## Decision

Use facts as source of truth and derive bird counts in the pure domain module. Facts are:
- placement rows in flock_placements;
- deaths and culling on the flock/date daily_records row;
- bird counts on sales;
- paired source/target bird_transfers rows represented by one atomic transfer fact.

For a date, derive remaining birds as placed − deaths − culling − birds sold − transfers out + transfers in. Never expose an editable closing-bird field. A write validates the affected flock chain and rejects any negative closing count. Editing an allowed fact records before/after in audit_events and recalculates from its effective date. A transfer affects both flocks in one transaction. Closed-flock edits are rejected unless the separate reopen workflow authorizes them with a reason.

Daily records remain editable facts within the approved role/time windows, so the database audit history records changes. The design does not require an append-only generic event bus or event sourcing every field.

## Consequences

- Rebuilding totals from facts is deterministic and supports a consistency test.
- Daily history reads need tenant/flock/date indexes; list queries paginate.
- Projection caches may accelerate reads but are disposable and cannot become authoritative.
- Exact ordering for same-day sale/transfer/death events and transfer-date boundaries must be specified before implementation if it affects negative-count validation. Do not invent ordering.
- Flock placement weight and bird movement weight do not alter the bird-count equation.
