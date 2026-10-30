# Phase plan

Phases are numbered in the sequence used for the product work. Do not begin the next phase until its exit test passes and the product owner says go.

| Phase | Outcome | Exit test |
|---|---|---|
| 0 — Product package | Requirements, roles, scope, formulas, risks, and plan | Owner approval. Passed on 2026-10-12; later confirmations are listed in `decisions.md` and `formulas.md`. |
| 1 — Design package | System diagram, module boundaries, ERD, role-aware API outline, ADRs, mobile wireframes, design tokens/navigation, traceability | Owner approval of ERD, API outline, and wireframes; traceability covers MVP requirements. Passed on 2026-10-12. |
| 2 — Platform foundation | Monorepo, PostgreSQL Compose, environment configuration, toolchains, test harnesses, Alembic baseline, logging, health/readiness, CI, scripts, i18n, responsive route-split shell | Fresh clone starts PostgreSQL, API, and frontend; migrations apply; CI and health/readiness checks pass. The repository contains this foundation, but a dated exit result is not recorded here. |
| 3 — Tenant and identity foundation | Database/migrations, tenant context, authentication, roles, audit primitives | Identity migration applies; cross-tenant and authorization checks pass; mypy and Ruff pass. Passed on 2026-10-16. Invite-only onboarding is confirmed; invitation delivery remains a deployment seam. |
| 4 — Farm operations vertical slice | Farm/shed/flock setup, placement, daily records, weights, edits, close/reopen | Authorized end-to-end flock workflow, idempotent daily entry, gap flags, audit/recompute, negative-count rejection, and role checks pass. Implementation evidence exists in later phase checks; a separate Phase 4 exit result is not recorded here. |
| 5 — Domain foundation | Pure calculations and verified fact-to-total rules | Table/property tests and approved 5,000-bird candidate pass at 95%+ domain coverage. Candidate assumptions A1–A9 and corrected outputs approved 2026-10-23; focused checks recorded 95.69% coverage. PostgreSQL integration requires `TEST_DATABASE_URL`. |
| 6 — Daily operations and mobile entry | Idempotent daily records, edit/recompute, feed purchases/use, weekly weights, mobile entry | Mobile entry, duplicate submission, backdated recompute/audit, role windows, and quality checks pass. Local checks passed 2026-10-26; 2 PostgreSQL integration checks were skipped without `TEST_DATABASE_URL`. The 57.14 ms submit p95 used in-memory SQLite and is not a production latency result. |
| 7 — Dashboards and alerts | Operational dashboard, projections, configurable operational alerts | Realistic data: read p95 below 300 ms, dashboard p95 below 500 ms, no N+1 growth, indexed query plans, pagination, and configured alert thresholds. Local synthetic p95 evidence is recorded in ADR 0012: farms 230.49 ms, flocks 182.41 ms, dashboard 463.41 ms. Full exit-test status is not recorded. |
| 8 — Finance | Sales, payments, expenses, supplier links, derived and separately labelled profit | PostgreSQL/domain consistency, audit, buyer balances, estimated/actual profit examples, and authorization checks pass. Finance implementation conventions are recorded in ADRs 0009–0010; a complete Phase 8 exit result is not recorded. |
| 9 — Reports | Paginated operational/finance reports and CSV/PDF exports | Role/tenant-scoped reports, filters, pagination, export memory/runtime budget, and query performance pass. Report decisions are in ADR 0011; a complete Phase 9 exit result is not recorded. |
| 10 — Release readiness | Production deployment, observability, backup/restore, security, and performance evidence | Ruff, ESLint, type checks, builds, full tests, authorization/cross-tenant checks, restore rehearsal, secret scan, CORS/auth review, measured latency/Lighthouse, hosting, and backup policy are approved. Not complete: `security.md` lists open release gates; local synthetic measurements do not establish hosted performance. |
| 11 — Deployment | Production configuration and HTTPS, OCI images, release migrations, managed PostgreSQL backups, staging/custom domain, monitoring, tenant provisioning, and rollback | Main deploys to staging then production; restore into a fresh database and rollback are rehearsed; health/uptime alerts fire in a test. In progress: portable artifacts are present, but hosting/database provider, domains, secrets, hosted error tracking, and rehearsals are not configured. See `docs/deployment/phase11.md`. |
| 12 — Release and business readiness | Operational readiness, customer support, launch controls, and first-client readiness | To be defined with the owner after Phase 11 passes. Not started. |

## Recorded approvals and status

- **Phase 0:** Passed by owner on 2026-10-12. The Phase 5 candidate fixture and its A1–A9 assumptions/corrections were approved on 2026-10-23. The fixture is synthetic and does not cover missing-day behavior.
- **Phase 1:** Passed by owner on 2026-10-12.
- **Phase 3:** Passed on 2026-10-16: identity migration applied, mypy passed, 15 backend tests passed, and Ruff lint/format passed. Invite-only onboarding was confirmed during this phase.
- **Phase 5:** Approved candidate and focused domain results are recorded above. This approval is for that synthetic candidate and does not settle product-wide formula edge cases.
- **Phase 6:** Local exit checks passed on 2026-10-26 with the PostgreSQL integration skips and local-only latency limitation noted above.
- **Phase 7:** ADR 0012 records local synthetic p95 measurements at 16 workers and 50 requests per endpoint. Full dashboard/alert exit evidence is not recorded as passed.
- **Phase 8:** Finance implementation decisions exist in ADRs 0009–0010. Full exit evidence is not recorded as passed.
- **Phase 9:** Report implementation decisions exist in ADR 0011. Full exit evidence is not recorded as passed.
- **Phase 10:** In progress; do not treat as passed while release gates remain open.
