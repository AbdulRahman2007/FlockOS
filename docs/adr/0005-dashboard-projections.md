# ADR 0005: Dashboard projections and invalidation

- Status: Proposed for review
- Date: 2026-10-12

## Context

Read APIs target p95 below 300 ms and dashboard p95 below 500 ms on realistic data. Dashboards must use indexed or pre-aggregated data, avoid full-table scans and N+1 queries, and show values derived from facts. Stored aggregates must be rebuildable and consistency-tested.

## Options

1. Recompute every dashboard metric from all operational tables on each page load.
2. Maintain disposable, versioned dashboard snapshots from source facts and invalidate them when relevant facts change.
3. Store mutable totals on business rows and treat them as authoritative.

## Decision

Choose option 2. Keep normalized facts authoritative. Build farm- and flock-level dashboard snapshots from tenant-scoped, indexed fact queries using the same pure domain functions as detail responses. Snapshots carry a projection version, computed timestamp, and stale marker; they are rebuildable and never used as write inputs.

When a relevant fact changes, the same PostgreSQL transaction marks affected snapshots stale and enqueues a projection refresh request. The invalidation is tenant-scoped and date-aware. Daily records invalidate their flock/farm views from the edited date forward; placements invalidate the flock and farm since placement; weight samples invalidate FCR views from the sample date; sale/transfer facts invalidate affected flocks, farms, and buyer finance; feed-stock and expense facts invalidate the corresponding farm/flock finance projections. Transfer invalidates both source and destination.

A projection worker claims refresh requests safely (for example, row locking with SKIP LOCKED), rebuilds only the affected tenant/farm/flock/date range using indexed queries, and atomically replaces snapshots. If a read encounters a stale snapshot before refresh completes, return the last snapshot with its `computed_at` as the as-of time and an explicit stale marker. If no snapshot exists, use an indexed bounded rebuild for that scope. Never imply stale data is current and never fall back to an unbounded table scan. Add a fact-to-projection consistency test and query-count/performance measurements.

## Consequences

- Dashboard response cost is controlled by tenant/farm/flock and date indexes, while writes do not make projections authoritative.
- Refresh work may lag; UI must show freshness timestamp and an understandable stale/retry state if bounded rebuild is not ready.
- A transactional refresh queue and worker are extra operational pieces; begin with the simplest reliable worker and measure before adding broker infrastructure.
- Projection versioning permits formula changes and complete rebuilds from the same source facts.
- Refresh freshness lag remains a measurable operational target to set; latency targets must be measured, not assumed.
