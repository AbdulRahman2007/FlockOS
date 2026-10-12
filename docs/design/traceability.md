# MVP requirement traceability

This table maps the Phase 0 requirements to proposed persistence, API, and visible screen surfaces. Platform-wide requirements apply to every listed record/API/screen; they still have explicit representative anchors. IDs are stable references for design review, not code identifiers.

| ID | MVP requirement | Table(s) | Endpoint(s) | Screen(s) |
|---|---|---|---|---|
| F-01 | Farm → shed → flock product loop | farms, sheds, flocks | GET/POST /farms; GET/POST /farms/{id}/sheds; GET/POST /flocks | Farms, Flock list, Flock detail |
| F-02 | Tenant isolation; server derives tenant | tenants, users, all tenant tables | All /api/v1 tenant routes | All authenticated screens |
| F-03 | Derived bird counts; no hand-edited totals | flock_placements, daily_records, sales, bird_transfers | GET /flocks; GET /flocks/{id}; POST/PATCH record routes | Dashboard, Flock detail |
| F-04 | Daily record fields, unique flock/date, idempotent submit | daily_records, idempotency_keys | POST/PATCH /flocks/{id}/daily-records | Single-screen Daily entry, Daily history |
| F-05 | Missed dates are flagged, never zero-filled | daily_records | GET /flocks/{id}/record-gaps | Dashboard, Flock detail |
| F-06 | Weekly weight samples separate from daily entry | weight_samples | GET/POST/PATCH /flocks/{id}/weight-samples | Flock detail → Weights |
| F-07 | Partial sale records with buyer/date/birds/weight/rate/amount | buyers, sales | GET/POST/PATCH /sales | Sales, Flock detail → Sales |
| F-08 | Payments separate; buyer outstanding derived | sale_payments, sales, buyers | GET/POST /sales/{id}/payments; GET /reports/finance | Sales, Buyer balance, Finance dashboard |
| F-09 | Per-farm feed stock; bag conversion; opening/purchase/use/return/adjustment | farm_feed_settings, feed_stock_events, daily_records, farms, suppliers, expenses | GET/PUT /farms/{id}/feed-settings; GET/POST /farms/{id}/feed-stock/events | Feed stock, Daily entry, Flock detail → Feed |
| F-10 | Suppliers linked to feed purchases and expenses; no payables ledger | suppliers, feed_stock_events, expenses | GET/POST/PATCH /suppliers; GET/POST /expenses | Suppliers, Feed purchase, Expenses |
| F-11 | Configurable in-app mortality/gap/feed-cover/FCR alerts | alert_rules, alerts, daily_records, feed_stock_events, weight_samples | GET /alerts; GET/PUT /alert-rules | Dashboard alerts, Alert settings |
| F-12 | Estimated profit uses entered market price; actual profit uses recorded sales; keep results separate and labeled | flock_market_price_events, sales, sale_payments, expenses, dashboard_snapshots | GET/POST /flocks/{id}/market-price-estimates; GET /dashboard/finance; GET /reports/finance | Flock detail → Finance, Finance dashboard, Finance report |
| F-13 | Edit audit (actor/time/before/after) | audit_events, daily_records, sales, expenses | PATCH daily/sales/expenses; GET /audit-events | Edit history, Audit log |
| F-14 | Recompute from edited date; reject negative closing count | flock_placements, daily_records, sales, bird_transfers | PATCH /daily-records/{id}; PATCH /sales/{id}; POST /bird-transfers | Daily entry correction, Flock detail |
| F-15 | Closed flock lock; Owner/Super Admin reopen with reason | flocks, audit_events | POST /flocks/{id}/close; POST /flocks/{id}/reopen | Flock detail, Reopen confirmation |
| F-16 | Roles, assigned farm scoping, deny by default | users, user_farm_assignments | All endpoints; GET/PATCH /users | Role-filtered navigation, User management |
| F-17 | Invite-only onboarding if P2 is confirmed | users, auth_sessions | POST /admin/tenants; POST /users/invitations | Tenant setup, User invitations |
| F-18 | In-app roles dashboards/reports | dashboard_snapshots, source fact tables | GET /dashboard/operations; GET /dashboard/finance; GET /reports/* | Operational dashboard, Finance dashboard, Reports |
| F-19 | Farm-local records in Asia/Karachi; UTC timestamps | farms, all dated business tables, audit_events | All date-bearing write/read endpoints | All date-bearing forms, histories, reports |
| F-20 | PKR exact money and kg fixed-precision weights | sales, sale_payments, expenses, feed_stock_events, weight_samples | All finance/weight/feed endpoints | Sales, Expenses, Feed, Flock weights |
| F-21 | REST, pagination, safe errors, OpenAPI, optimistic locking | idempotency_keys and all resource tables | All /api/v1 list/update routes | All list/forms; conflict/error states |
| F-22 | Argon2, short JWT + refresh, rate limit, CORS, least privilege | users, auth_sessions | /auth/*; all protected endpoints | Login, session-expired state |
| F-23 | Pure domain calculations, no frontend recomputation | Source fact tables and rebuildable snapshots | GET flock/dashboard/report endpoints | Flock detail, dashboards, reports |
| F-24 | Audit and tenant writes are transactional | audit_events, all edited fact tables | PATCH daily/sales/expenses; POST transfer/reopen | Forms, Audit log |
| F-25 | Record dead-bird weights separately to support FCR | mortality_weight_entries, daily_records | GET/POST /daily-records/{id}/mortality-weights | Flock detail → Mortality weights / Daily history |
| N-01 | API read p95 <300 ms; dashboard p95 <500 ms | dashboard_snapshots and indexed source tables | All read APIs, especially /dashboard/* | Dashboard, list/detail screens |
| N-02 | Pagination and no N+1 list queries | source resource tables | All GET collection/report endpoints | Farms, flocks, sales, expenses, reports |
| N-03 | Dashboard indexed/pre-aggregated, no full scans | dashboard_snapshots, projection_refresh_jobs, indexed source tables | GET /dashboard/* | Operational and finance dashboards |
| N-04 | Initial JS <200 KB gzipped; route code splitting | N/A (frontend build artifact) | N/A (route loading) | All routes |
| N-05 | LCP <2.5 s on mid-range Android/4G; Lighthouse mobile ≥90 | N/A (frontend build/runtime) | Read APIs under measured realistic load | Dashboard and Daily entry |
| N-06 | Query caching, sensible stale times, optimistic daily update | idempotency_keys, daily_records | POST/PATCH daily records; GET resources | Daily entry and query-backed screens |
| N-07 | Mobile-first; minimum 44 px targets; numeric keypad/defaults | N/A (presentation) | Daily and weight write routes | Daily entry, Weight entry |
| N-08 | Preserve typed draft and retry after failures; online-only v1 | idempotency_keys, daily_records | POST daily record with same idempotency key | Daily entry, retry/error state |
| N-09 | Plain labels, inline validation, loading/empty/error states | Source table per route | All data endpoints | Every screen and form |
| N-10 | Confirm destructive actions; charts not color-only | N/A (presentation) | Close/reopen and archive routes | Confirmation dialogs, dashboards |
| N-11 | UI strings in i18n; CSS logical properties/Urdu seam | N/A (frontend resources) | N/A | All screens/locales |
| N-12 | Real PostgreSQL integrations, domain properties, Playwright flows | All persistence tables | All APIs covered by test flows | Core daily, sales, role flows |
| N-13 | Golden 5,000-bird/35-day fixture matches spreadsheet | All source fact tables used by formulas | Domain calculation paths surfaced by flock/report reads | Flock detail and reports |
| N-14 | Every endpoint × role and cross-tenant attempts tested | users, user_farm_assignments, tenant-owned tables | Every protected endpoint/method | Every role-visible screen plus denial states |
| N-15 | Ruff/ESLint/type/build clean; no secrets in source | N/A (repository/config) | N/A (CI quality gate) | N/A (release gate) |

## Traceability review notes

- Every functional and non-functional Phase 0 requirement has at least one table, endpoint, and screen/build surface. For presentation/build-only requirements, table or endpoint is marked N/A because no database/API resource should be invented to satisfy a UI quality target.
- Proposed P2 invite-only behavior remains conditional; no public signup endpoint is designed.
- FCR traceability depends on an approved source for dead-bird weights, called out in erd.md.
- Exact system/health visibility and alert management follow API outline assumptions until explicitly assigned beyond the approved role matrix.
