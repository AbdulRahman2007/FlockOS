# Requirements

Status: Phase 0 baseline derived from `decisions.md` and `AGENTS.md`. Items tied to proposed decisions remain pending confirmation.

## Functional requirements

### Farm operations and records
- Support the farm → shed → flock → daily record → mortality/feed/weight → calculations → dashboard → reports workflow.
- Maintain tenant isolation: every business record belongs to a tenant; the server derives tenant context from the authenticated user.
- Track flock placement and bird movement facts. Derive closing birds; never allow users to hand-edit calculated totals.
- Record one daily record per flock and farm-local date, with deaths, culling, feed used, water, temperature, and notes. Enforce uniqueness and idempotent submission. Flag missing dates; never synthesize zero records.
- Track weekly weight samples separately, including sample size and average weight.
- Permit partial sales and record buyer, date, birds, total weight, rate/kg, amount, and amount paid. Show outstanding balances by buyer.
- Keep feed stock per farm. Track opening stock, purchases, usage, returns, and adjustments; convert bags to kg using a configurable bag size.
- Track suppliers as a simple list linked to feed purchases and expenses; do not implement a payables ledger in v1.
- Provide configurable in-app alerts for high mortality, missing daily records, low feed cover, and FCR worse than target. Vaccination alerts are deferred.
- Separate estimated profit from actual profit and label each clearly.
- Audit edits to daily records, sales, and expenses with actor, timestamp, and old/new values. Recompute derived records from the edited date; reject negative closing bird counts.
- Lock closed flocks. Only Owner or Super Admin may reopen, with a reason.

### Access, API, and persistence
- Apply deny-by-default RBAC to every endpoint and enforce tenant scope in every repository query.
- Use REST under `/api`, consistent safe error responses, pagination, OpenAPI docs, optimistic locking for shared records, and idempotent daily record creation.
- Use normalized PostgreSQL data, migrations only, explicit transactions, foreign keys, NOT NULL and check constraints, unique flock/date records, and indexes for dashboard/report access.
- Use environment-based configuration, Argon2 password hashes, short-lived access JWTs plus refresh, login rate limiting, CORS allow-list, and least-privilege database credentials.
- Keep critical calculations as pure functions in one backend domain module. The domain imports no FastAPI, SQLAlchemy, or HTTP code; the frontend displays server results and does not recalculate them.
- Store facts rather than mutable totals. Any persisted aggregate must be rebuildable from facts and covered by a consistency test.

## Non-functional requirements

### Performance and scale targets
- Measure API read endpoint p95 below 300 ms and dashboard p95 below 500 ms on realistic data.
- Paginate all list endpoints; prevent N+1 query growth and test list query counts.
- Dashboard queries use indexed or pre-aggregated data and avoid full-table scans.
- Frontend initial JavaScript is below 200 KB gzipped; route-level code splitting is required.
- Target LCP below 2.5 seconds on a mid-range Android phone over 4G, and Lighthouse mobile performance and accessibility scores of at least 90. Record test conditions and actual measurements.
- Use TanStack Query caching with suitable stale times and optimistic updates for daily entry.

### Usability and localization
- Design mobile-first for workers using phones in sheds. Interactive targets are at least 44 px.
- Numeric fields request a numeric keypad; forms use sensible defaults and daily entry takes as few taps as practical.
- Preserve typed data when submission fails. Show inline validation with a clear correction, plus loading, empty, and error states on every screen.
- Confirm destructive actions. Charts must communicate meaning without relying on color alone.
- Keep all UI text in i18n resource files. Use CSS logical properties and leave an Urdu/RTL seam.
- v1 is online-only; drafts and retry behavior are required. Offline synchronization is later.

### Data, time, and quality
- Store money as exact NUMERIC in PKR, never floating point. Store weights in kg at fixed precision.
- Store UTC timestamps and farm-local dates in Asia/Karachi.
- Test domain rules with table-driven and property-based tests; integration tests use real PostgreSQL; include a small number of Playwright flows.
- Maintain the hand-calculated 5,000-broiler/35-day golden fixture and match it exactly.
- Test authorization for every endpoint/role combination and cross-tenant access attempts. Do not delete or weaken working tests to force a pass.
- Run Ruff, ESLint, type checks, builds, and tests as applicable before release. Do not claim performance targets without measurement.

## Open confirmation

P1 is approved with the final matrix in `roles.md`. P2–P6 in `decisions.md` remain proposed. Invite-only onboarding, one-tenant-per-user assignments, production hosting, and year-one scale remain pending owner approval. Formula edge cases are tracked in `formulas.md`; core worked examples and FCR/profit definitions have owner approval.
