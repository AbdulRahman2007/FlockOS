# ADR 0004: Authentication and authorization

- Status: Proposed for review
- Date: 2026-10-12

## Context

The API requires Argon2 password hashes, short-lived JWT access tokens plus refresh, login rate limiting, deny-by-default RBAC, farm scoping, safe errors, CORS allow-list, and least-privilege database access. The approved P1 matrix includes Super Admin, Owner, Manager, Worker, and Accountant.

## Options

1. Long-lived bearer token with role checks only in the frontend.
2. Short-lived access JWT plus rotating refresh session, with server-side role/tenant/farm authorization on every API operation.
3. Third-party identity provider only, with no application-level role/tenant model.

## Decision

Choose option 2. Store only Argon2 password hashes. Issue short-lived signed access JWTs and opaque refresh tokens whose hashes are stored in auth_sessions; rotate refresh on use and support revocation. Login attempts are rate-limited. Validate issuer, audience, signature, expiry, and token/session state.

Resolve tenant, role, and farm assignments from trusted identity state. A tenant user belongs to one tenant; Manager/Worker requests are additionally constrained to assigned farms. Super Admin is a separate platform identity with no tenant business access by default. Every endpoint/method uses server-side authorization, deny by default, and returns the same safe not-found behavior for foreign-tenant and absent IDs. Frontend route guards improve navigation only and are not security controls.

Use an explicit CORS allow-list and a least-privilege database role. Keep access tokens short lived; refresh tokens are rotated/revocable. Invite delivery is conditional on confirmation of P2; no public signup route is designed.

## Consequences

- Authorization must be tested across endpoint × role and cross-tenant cases.
- Farm assignments need efficient tenant/user/farm indexes and must be applied to reports and exports, not just detail pages.
- Token refresh requires replay detection and safe session revocation semantics to finalize in implementation.
- Super Admin tenant management/reopen actions need narrow, audited service operations; they do not authorize tenant business-data browsing.
