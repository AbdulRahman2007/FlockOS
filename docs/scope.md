# Product scope

Status: Phase 0 draft based on confirmed D1–D14 and owner-approved P1 role matrix. P2–P6 remain proposals requiring confirmation before implementation.

## MVP (v1)

- Multi-tenant SaaS foundation with server-derived tenant context, tenant-scoped repositories, cross-tenant authorization tests, and an ADR evaluating PostgreSQL Row-Level Security.
- Core product loop: farms, sheds, flocks, daily records, mortality/culling, feed use, weekly weight samples, derived calculations, operational dashboard, and reports.
- Derived bird counts; daily/weekly/cumulative mortality; running and final raw FCR; per-farm feed stock; estimated and actual profit shown separately.
- Daily record uniqueness, idempotent submission, flagged gaps, permitted edits with audit, recomputation from edited date, negative-count rejection, flock close/reopen restrictions.
- Partial sales, buyer balances and payments; suppliers linked to feed purchases and expenses; expense records and audit trail.
- Configurable alerts for mortality, missing records, feed cover, and FCR.
- Tenant user and role management by the Owner follows approved P1. Invite-only onboarding remains subject to confirmation of proposed P2. Approved Super Admin, Owner, Manager, Worker, and Accountant permissions are documented in `roles.md`.
- Online-only mobile-first web app; draft retention and retry on failure; English UI with i18n/RTL-ready structure.
- PostgreSQL, migrations, REST API, frontend stack, security controls, and test strategy from `AGENTS.md`.

## Explicitly later / out of v1

- Offline sync.
- Vaccination alerts and vaccination workflows.
- Payables ledger.
- Billing and paid-plan enforcement (tenant plan/limit fields may be nullable seams only).
- Unconfirmed onboarding, hosting, and scale assumptions until approved.
- Other modules such as medicine, notifications, and fuller accounting unless needed for a confirmed v1 requirement.
- Additional languages beyond the English foundation and RTL-ready structure.

## Out of scope

- Public self-service signup (proposed P2 says invite-only; this remains pending).
- Hand-editing derived bird totals.
- Treating estimated market-price profit as actual sales profit.
- Treating missing daily records as zero activity.
- Unrecorded destructive changes or bypassing tenant isolation.
