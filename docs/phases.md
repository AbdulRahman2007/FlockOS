# Phase plan

Each phase is sequential. Do not start the next phase until its exit test passes and the product owner says go. Phase numbering follows the owner's current task sequence.

| Phase | Outcome | Exit test |
|---|---|---|
| 0 — Product package | Requirements, roles, scope, formulas, risks, and plan | Passed by the owner's explicit confirmation on 2026-10-12. P1 and the core worked formula examples are approved; P2–P6 remain documented proposals. |
| 1 — Design package | System diagram, module boundaries, ERD, role-aware API outline, ADRs, mobile wireframes, design tokens/navigation, traceability | Passed by owner approval of the ERD, API outline, and wireframes on 2026-10-12; traceability maps every MVP requirement to persistence, endpoint, and screen/build surface. |
| 2 — Platform foundation | Monorepo setup, PostgreSQL Compose, environment config, toolchains, test harnesses, empty Alembic baseline, structured logging, health/readiness, CI, scripts, i18n, responsive route-split shell | Fresh clone starts local PostgreSQL, API, and frontend using README commands; Alembic baseline applies; CI checks are green; health and readiness tests pass. |
| 3 — Domain foundation | Pure calculation module and verified fact-to-total rules | Table-driven and property-based tests cover birds, mortality, FCR, stock, costs/profit, and buyer balances; owner-provided 5,000-bird/35-day golden fixture matches the independent spreadsheet exactly; domain imports no framework/database/HTTP code. |
| 4 — Tenant and identity foundation | Database/migrations, tenant context, authentication, roles, audit primitives | Real PostgreSQL integration tests; every business table tenant-scoped; cross-tenant denial and authorization matrix pass; secrets absent; migrations apply from empty database; tenancy ADR disposition recorded. |
| 5 — Farm operations vertical slice | Farm/shed/flock setup, placement, daily records, weights, edits, close/reopen | End-to-end authorized flow records a flock through daily entries and a weight sample; idempotent retry creates one record; gaps are flagged; audit/recompute works; negative closing count rejected; allowed/denied role tests pass. |
| 6 — Feed, sales, expenses, and derived finance | Feed stock, suppliers, partial sales/payments, expenses, approved profit outputs | PostgreSQL integration and domain consistency tests reconcile facts to balances/stock; sales and expenses edits audited; buyer outstanding and estimated/actual profit match approved examples; authorization tests pass. |
| 7 — Dashboards, reports, and alerts | Operational/finance views, paginated reports, configurable alerts | Realistic dataset shows read p95 <300 ms and dashboard p95 <500 ms; list query-count tests show no N+1 growth; dashboard query plans avoid full-table scans; pagination and alert thresholds validated. |
| 8 — Mobile-first workflows | Accessible daily-entry and management flows, drafts/retries, user-facing states | Vitest/RTL and Playwright flows pass; touch targets ≥44 px; failed daily submissions preserve input; i18n/RTL structure is used; initial JS <200 KB gzipped; measured LCP <2.5 s and Lighthouse mobile performance/accessibility ≥90 or gaps explicitly approved. |
| 9 — Release readiness | Production deployment, observability, backup/restore, security and performance evidence | Ruff, ESLint, type checks, builds, full test suite, authorization matrix, cross-tenant suite, restore rehearsal, secret scan, CORS/auth review, and documented measured latency/Lighthouse results pass; production hosting and backup policy approved. |

## Phase 0 status

The owner explicitly marked Phase 0 passed on 2026-10-12. The exact golden-case inputs and independent spreadsheet outputs remain a Phase 3 prerequisite.

## Phase 1 status

The owner approved the ERD, API outline, and wireframes on 2026-10-12. Phase 1 is passed.

## Phase 1 decisions and remaining formula assumptions

The owner resolved four Phase 1 design points: record dead-bird weights separately; use liters and °C for water and temperature; estimate revenue from current live biomass (birds alive × latest average weight) at the latest applicable entered market price; and return a stale dashboard snapshot with its as-of time. Other formula edge cases and exact golden-case inputs remain open in `formulas.md`.
