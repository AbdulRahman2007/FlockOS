# Risks

Likelihood and impact use High / Medium / Low. Ratings are initial Phase 0 estimates and should be revisited at each phase exit.

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Tenant data leaks through a missing tenant filter or role check | Medium | Critical | Derive tenant from authenticated identity; require tenant context in repositories; deny by default; endpoint × role matrix; cross-tenant tests; evaluate PostgreSQL RLS in an ADR. |
| Formula ambiguity causes materially wrong flock or financial reporting | High | High | Owner approves each worked example and exact golden spreadsheet before calculation implementation; keep one pure domain module; use fixed precision and boundary/property tests. |
| Approved role permissions are inconsistently enforced across endpoints | Medium | High | Treat `roles.md` as the approved P1 matrix; deny by default; implement endpoint × role authorization tests and cross-tenant tests. Keep P2–P6 marked as proposals. |
| Daily entry failure loses worker input | Medium | High | Retain drafts, retry safely with idempotency, show clear failures, and test interrupted/duplicate submission flows. |
| Concurrent edits produce stale totals or overwrite data | Medium | High | Optimistic locking; explicit transactions; audit before/after values; deterministic recomputation from edited date. |
| Invalid event history yields negative birds or untrustworthy aggregates | Medium | High | Database checks where possible; pure derivation; reject negative closing birds; aggregate consistency tests. |
| Query volume or table scans make dashboard too slow as tenants grow | Medium | High | Pagination, indexed/pre-aggregated dashboard reads, realistic datasets, query-count test for N+1, and measured p95 targets. |
| Database loss or hosting-tier limits affect a paying farm | Medium | Critical | Confirm production provider and terms; paid managed PostgreSQL with daily backups for real client data (proposed P5); rehearse restore and monitor capacity. |
| Credentials or tokens are exposed | Low | Critical | Environment-only secrets, no committed `.env`, Argon2, short-lived access JWT plus refresh, login rate limiting, CORS allow-list, least-privilege database role. |
| Time-zone boundaries assign records to the wrong farm day | Medium | High | Persist UTC timestamps plus Asia/Karachi farm-local dates; test date boundaries and DST/time conversion behavior. |
| Poor connectivity or shed conditions make forms hard to use | High | Medium | Mobile-first, 44 px targets, numeric keypad, few taps, preserve draft/retry; clearly keep offline sync out of v1. |
| Scope expands into deferred modules before core loop is reliable | Medium | Medium | Use phased plan and exit gates; defer billing, offline sync, payables, and vaccination as documented. |
| Urdu/RTL retrofits require broad UI rework | Medium | Medium | Put strings in locale files from day one; use CSS logical properties; include RTL review before localization work. |
| Performance/accessibility targets are asserted without evidence | Medium | Medium | Record dataset, device/network, Lighthouse and latency results; gate release on measured targets and report deviations. |
