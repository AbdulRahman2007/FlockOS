# ADR 0012: Phase 10 release readiness and report index

- Status: Accepted
- Date: 2026-10-27

## Context

Phase 10 requires a repeatable, isolated load fixture, query-plan evidence, security and dependency review, accessibility checks, and measured mobile performance. Date-range feed reports filter daily facts by tenant and record date. The existing unique flock/date index begins with `tenant_id, flock_id`, which is not the best leading key for a tenant-wide date-range report.

## Decision

- Add `ix_daily_tenant_date_flock (tenant_id, record_date, flock_id)` by Alembic migration.
- Reuse the dashboard bird ledger already calculated for current-bird totals when constructing trend points. Keep all-time bird movement in SQL summaries and load only recent 30-day detail rows for trends.
- Keep the Phase 10 load fixture in a dedicated script. It creates 100 tenants, 1,000 users, 100 flocks, and three years of daily facts in a separate PostgreSQL database, then reports endpoint p95s and an `EXPLAIN (ANALYZE, BUFFERS)` plan.
- Treat dashboard under 500 ms and read endpoints under 300 ms as release gates; do not waive failed measurements in the report.

## Consequences

- PostgreSQL used the new composite index for the seeded three-year tenant/flock/date query (0.084 ms execution time).
- Final local synthetic p95 at 16 workers (50 requests per endpoint): farms 230.49 ms, flocks 182.41 ms, dashboard 463.41 ms, feed report 297.58 ms. All local budgets passed after limiting dashboard detail rows to 30 days and retaining all-time totals as SQL aggregates.
- Re-run against production-like hardware and data distribution before launch; local synthetic measurements do not establish hosted performance.
- The added index costs storage and write work for daily records; validate its value with production query plans after deployment.
