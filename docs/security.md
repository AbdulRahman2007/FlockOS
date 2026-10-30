# Security review

Review date: 2026-10-27. Scope: source-level OWASP Top 10:2025 review, npm dependency audit, and focused authorization/authentication tests. This is not a penetration test. See the [OWASP Top 10:2025](https://top10.owasp.org/2025/) for category definitions.

## Checklist

| Category | Evidence reviewed | Status / follow-up |
|---|---|---|
| A01 Broken Access Control | Permission dependencies on business routes; tenant-bound repository and farm scope; role matrix and cross-tenant tests | Implemented and covered by tests. Re-run PostgreSQL authorization suite before deployment. |
| A02 Security Misconfiguration | CORS allow-list; production cookie flags; settings defaults | Production startup now rejects the known development JWT secret. Add deployment security headers and verify production CORS/TLS at the hosting edge. |
| A03 Software Supply Chain Failures | `npm audit` against `frontend/package-lock.json`; attempted isolated `pip-audit` | Frontend audit clean: 0 vulnerabilities. Python advisory audit remains open because the isolated scanner installation stalled before producing a result. |
| A04 Cryptographic Failures | Argon2 password hashes; SHA-256 digests for opaque refresh/invitation tokens; short-lived signed access tokens | Implemented. Production must provide a unique secret and TLS. |
| A05 Injection | SQLAlchemy ORM/query construction and request validation | Reviewed; no user-controlled SQL construction found in inspected API paths. Re-run static checks in CI. |
| A06 Insecure Design | Tenant context, idempotency, optimistic locking, audit trail, approved domain rules | Covered by existing unit/integration tests. PostgreSQL integration checks and full threat modeling remain outstanding. |
| A07 Authentication Failures | Login attempt rate limit; active-user/session checks; refresh rotation/replay handling; secure HttpOnly refresh cookie | Implemented. Bootstrap/invitation require 12 characters but do not reject weak patterns; use a strong unique credential for any shared environment. |
| A08 Software or Data Integrity Failures | Locked npm dependency graph; Alembic-only schema changes; migration/test workflows | Implemented. Protect CI/deployment credentials and require reviewed dependency updates. |
| A09 Logging & Alerting Failures | Structured logs, request IDs, audit facts | Request errors are correlated. Production log retention, alert routing, and security-event monitoring are not configured in this repository. |
| A10 Mishandling of Exceptional Conditions | Shared validation/HTTP error formats; generic unexpected 500 responses | Implemented. Database and upstream failure behavior still needs production integration verification. |

## Findings and release gates

| ID | Severity | Finding | State |
|---|---|---|---|
| SEC-01 | High | The built-in development JWT secret could previously be used when `APP_ENVIRONMENT=production`. | Fixed: production settings validation now rejects that default; covered by tests. |
| SEC-02 | Moderate | `fast-uri` versions in the frontend lockfile had published advisories. | Fixed with a semver-safe npm audit update; follow-up audit reports 0 vulnerabilities. |
| SEC-03 | Open | Python dependencies have not been checked against an advisory database; temporary scanner installation stalled before audit output. | Open; add/run `pip-audit` in CI or a network-enabled environment. |
| SEC-04 | Open | The local bootstrap credential was supplied in chat and is not appropriate for any shared or production environment. | Rotate before using shared data or exposing the API. No password-change screen exists yet. |
| SEC-05 | Verified for the local synthetic load | The seeded 100-tenant/1,000-user fixture contains 109,500 daily records over three years. With 16 concurrent workers and 50 requests per endpoint, final p95 was farms 230.49 ms, flocks 182.41 ms, dashboard 463.41 ms, and feed report 297.58 ms. | All measured endpoint budgets met (300 ms reads, 500 ms dashboard). The three-year tenant/flock/date query used `ix_daily_tenant_date_flock`, with 0.084 ms PostgreSQL execution time. Repeat on production-like hardware before launch. |
| SEC-06 | Open | Lighthouse mobile scores have not yet been collected on key pages. | Run against production-like deployment conditions and retain reports. |

Phase 10 is not complete until the open release gates above are closed or explicitly accepted by the product owner.
