# Phase plan

Each phase is sequential. Do not start the next phase until its exit test passes and the product owner says go. Phase numbering follows the owner's current task sequence.

| Phase | Outcome | Exit test |
|---|---|---|
| 0 â€” Product package | Requirements, roles, scope, formulas, risks, and plan | Passed by the owner's explicit confirmation on 2026-10-12. P1 and core worked formula examples are approved; P2 was confirmed in Phase 3; P3-P6 remain documented proposals. |
| 1 â€” Design package | System diagram, module boundaries, ERD, role-aware API outline, ADRs, mobile wireframes, design tokens/navigation, traceability | Passed by owner approval of the ERD, API outline, and wireframes on 2026-10-12; traceability maps every MVP requirement to persistence, endpoint, and screen/build surface. |
| 2 â€” Platform foundation | Monorepo setup, PostgreSQL Compose, environment config, toolchains, test harnesses, empty Alembic baseline, structured logging, health/readiness, CI, scripts, i18n, responsive route-split shell | Fresh clone starts local PostgreSQL, API, and frontend using README commands; Alembic baseline applies; CI checks are green; health and readiness tests pass. |
| 3 - Tenant and identity foundation | Database/migrations, tenant context, authentication, roles, audit primitives | Identity schema migrated successfully; cross-tenant repository and API tests, route permission coverage, and the authorization matrix pass; mypy and Ruff pass. |
| 4 â€” Farm operations vertical slice | Farm/shed/flock setup, placement, daily records, weights, edits, close/reopen | End-to-end authorized flow records a flock through daily entries and a weight sample; idempotent retry creates one record; gaps are flagged; audit/recompute works; negative closing count rejected; allowed/denied role tests pass. |
| 5 â€” Domain foundation | Pure calculation module and verified fact-to-total rules | Table-driven and property-based tests cover birds, mortality, FCR, stock, costs/profit, and buyer balances; owner-approved 5,000-bird/35-day candidate matches the approved corrected outputs under A1-A9; domain coverage is at least 95%; domain imports no framework/database/HTTP code. |
| 6 â€” Daily operations and mobile entry | Idempotent daily records, edit/recompute, feed purchases and use, weekly weights, mobile entry | Mobile Playwright flow submits in six taps; duplicate submit creates one row; backdated edits recompute counts; role windows pass; report measured submit p95. |
| 7 â€” Sales, expenses, and derived finance | Partial sales/payments, expenses, approved profit outputs | PostgreSQL integration and domain consistency tests reconcile finance facts; edits are audited; buyer outstanding and estimated/actual profit match approved examples; authorization tests pass. |
| 8 â€” Dashboards, reports, and alerts | Operational/finance views, paginated reports, configurable alerts | Realistic dataset shows read p95 <300 ms and dashboard p95 <500 ms; list query-count tests show no N+1 growth; dashboard query plans avoid full-table scans; pagination and alert thresholds validated. |
| 9 â€” Mobile-first workflows | Accessible management flows, drafts/retries, user-facing states | Vitest/RTL and Playwright flows pass; touch targets â‰¥44 px; failed submissions preserve input; i18n/RTL structure is used; initial JS <200 KB gzipped; measured LCP <2.5 s and Lighthouse mobile performance/accessibility â‰¥90 or gaps explicitly approved. |
| 10 â€” Release readiness | Production deployment, observability, backup/restore, security and performance evidence | Ruff, ESLint, type checks, builds, full test suite, authorization matrix, cross-tenant suite, restore rehearsal, secret scan, CORS/auth review, measured latency/Lighthouse results, hosting, and backup policy are approved. |

## Phase 0 status

The owner explicitly marked Phase 0 passed on 2026-10-12. The Phase 5 candidate fixture and its A1-A9 assumptions/corrections were approved on 2026-10-23. The fixture is synthetic and does not cover missing-day behavior.

## Phase 1 status

The owner approved the ERD, API outline, and wireframes on 2026-10-12. Phase 1 is passed.

## Phase 1 decisions and remaining formula assumptions

The owner resolved four Phase 1 design points: record dead-bird weights separately; use liters and °C for water and temperature; estimate revenue from current live biomass (birds alive × latest average weight) at the latest applicable entered market price; and return a stale dashboard snapshot with its as-of time. Phase 5 candidate-specific assumptions are recorded in `formulas.md`.

## Phase 5 status

The owner approved candidate-specific assumptions A1-A9 and corrected expected outputs on 2026-10-23. The focused domain suite, import-lint, table/property tests, and candidate regression pass with 95.69% domain coverage. PostgreSQL integration tests require `TEST_DATABASE_URL`.

## Phase 6 status

Local Phase 6 exit checks passed on 2026-10-26. The backend suite reports 62 passed and 2 PostgreSQL integration checks skipped because `TEST_DATABASE_URL` is not configured; domain calculation coverage is 95.19%. Mobile Playwright checks passed at a 390×844 viewport: a normal full-day entry takes six actions, and a separate double-click check sends one create request. Backend tests verified one stored row on duplicate submission, backdated recomputation/audit, and role edit windows. Submit p95 measured 57.14 ms for 15 requests through local TestClient with in-memory SQLite. This is a local harness measurement, not a production latency result. Ruff, mypy, frontend Vitest, ESLint, type-check, build, and the focused Playwright run pass. Review the skipped PostgreSQL checks with a configured test database before production sign-off; Phase 7 remains gated on the owner's go-ahead.

## Phase 3 status

Tenant identity foundation passed on 2026-10-16: migration applied, mypy passed, 15 backend tests passed, Ruff lint and format passed. Invite-only onboarding is confirmed by the Phase 3 task; invitation delivery remains a deployment seam.
