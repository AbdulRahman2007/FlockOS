# API outline

Status: Design proposal. Role access follows docs/roles.md; all unlisted operations are denied. Tenant identity is always taken from the authenticated principal, never request bodies or query parameters.

## API conventions

- Base path: /api/v1; HTTPS JSON; UUID identifiers.
- All list routes use page, page_size (with a server maximum), optional documented filters, and stable sorting. Responses include items, page, page_size, total (or an explicitly selected cursor form).
- Shared mutable resources return a version. Updates require If-Match/expected version; stale writes return 409 VERSION_CONFLICT.
- POST daily-record create requires Idempotency-Key. Same key and body replays the saved response; same key with a different body returns 409 IDEMPOTENCY_KEY_REUSED.
- Consistent errors: {"error":{"code":"...","message":"Safe user-facing summary","field_errors":{},"request_id":"..."}}. Never expose SQL, stack traces, tokens, or cross-tenant record existence.
- tenant_id is not accepted as a write field. Repository scope comes from token context; a foreign-tenant ID returns the same safe 404 used for an absent ID.
- No hard-delete endpoints for business facts. Correct eligible records through audited, versioned edits; use explicit archive/close workflows where applicable.
- Finance endpoints return PKR decimals as JSON decimal strings. Quantities identify confirmed units; water is liters and temperature is °C.
- Role shorthand: SA = Super Admin, O = Owner, M = Manager assigned farms, W = Worker own entries/limited views, A = Accountant. V = read only. Scopes and edit windows are defined in roles.md.

## Endpoint matrix

| Method + path | Purpose | Permitted roles and scope |
|---|---|---|
| POST /auth/login | Exchange credentials for short-lived access token and refresh session | Public; rate-limited |
| POST /auth/refresh | Rotate refresh token and issue access token | Auth session holder |
| POST /auth/logout | Revoke current refresh session | Auth session holder |
| GET /auth/me | Current identity, role, farm assignments, locale | O, M, W, A, SA (own identity only) |
| GET /health/live | Process liveness, no dependency details | Public; no business data |
| GET /health/ready | Dependency/readiness status | SA |
| GET /admin/tenants | Paginated tenant list | SA |
| POST /admin/tenants | Create tenant and initial Owner identity | SA; onboarding mechanics pending P2 |
| GET /admin/tenants/{tenant_id} | View tenant administration fields | SA |
| PATCH /admin/tenants/{tenant_id} | Update tenant status/administrative fields; no billing actions | SA |
| GET /tenant | Current tenant profile | O; other tenant roles only if fields are needed by allowed screens |
| GET /users | Tenant users list | O |
| POST /users/invitations | Invite user and assign role/farms | O; delivery integration pending |
| PATCH /users/{user_id} | Change role, farm assignments, or deactivate | O |
| GET /farms | Tenant farms filtered to role scope | O all; M assigned; W/A view |
| POST /farms | Create farm | O |
| GET /farms/{farm_id} | Farm detail | O all; M assigned; W/A view |
| PATCH /farms/{farm_id} | Edit farm | O; M assigned farm |
| GET /farms/{farm_id}/feed-settings | Read configured bag size | O; M assigned; W/A view |
| PUT /farms/{farm_id}/feed-settings | Change bag-size conversion for future entries | O only until finer permission is approved |
| GET /farms/{farm_id}/sheds | List sheds | O; M assigned; W/A view |
| POST /farms/{farm_id}/sheds | Create shed | O; M assigned farm |
| PATCH /sheds/{shed_id} | Edit shed | O; M assigned farm |
| GET /flocks | Paginated flocks and derived current-bird display | O all; M assigned; W/A view |
| POST /flocks | Create flock | O; M assigned farm |
| GET /flocks/{flock_id} | Flock detail and derived totals | O; M assigned; W/A view |
| PATCH /flocks/{flock_id} | Edit allowed flock metadata | O; M assigned; close rules still apply |
| POST /flocks/{flock_id}/placements | Add placement fact | O; M assigned |
| GET /flocks/{flock_id}/market-price-estimates | List entered market-price facts | O; M assigned; A |
| POST /flocks/{flock_id}/market-price-estimates | Record entered PKR/kg estimate as a fact | O; M assigned; A |
| GET /flocks/{flock_id}/daily-records | Paginated records/date range | O; M assigned; W own entries; A view |
| POST /flocks/{flock_id}/daily-records | Idempotent daily entry | O; M assigned within 7-day window; W own entry same day |
| PATCH /daily-records/{record_id} | Correct daily facts; audit and recompute from date | O anytime; M within 7 days; W own same-day entry |
| GET /daily-records/{record_id}/mortality-weights | List separate dead-bird weight entries | O; M assigned; W own same-day entry; A view |
| POST /daily-records/{record_id}/mortality-weights | Record dead-bird count and total weight for that day's deaths | O; M assigned; W own same-day entry |
| GET /flocks/{flock_id}/record-gaps | Missing-date flags; never synthesizes records | O; M assigned; W limited assigned flock; A view |
| GET /flocks/{flock_id}/weight-samples | List weekly samples | O; M assigned; W own entries; A view |
| POST /flocks/{flock_id}/weight-samples | Add sample/average weight | O; M assigned; W own same-day entry |
| PATCH /weight-samples/{sample_id} | Correct eligible sample | O; M assigned; W own same-day entry |
| GET /flocks/{flock_id}/transfers | List inbound/outbound transfer facts | O; M assigned; W/A view |
| POST /bird-transfers | Transfer birds between same-tenant flocks atomically | O; M only when both farms are assigned |
| GET /buyers | Paginated buyer list | O; M assigned farms; A |
| POST /buyers | Add buyer | O; M assigned; A |
| GET /sales | Paginated sales and filters | O; M assigned; A |
| POST /sales | Record partial or complete sale | O; M assigned; A |
| GET /sales/{sale_id} | Sale detail | O; M assigned; A |
| PATCH /sales/{sale_id} | Edit sale; audit, optimistic version | O; M assigned; A |
| POST /sales/{sale_id}/payments | Record payment fact | O; M assigned; A |
| GET /sales/{sale_id}/payments | List payment facts | O; M assigned; A |
| GET /suppliers | Paginated simple supplier list | O; M assigned; A view |
| POST /suppliers | Add supplier | O; M assigned |
| PATCH /suppliers/{supplier_id} | Edit supplier details | O; M assigned |
| GET /farms/{farm_id}/feed-stock | Current derived feed stock and event summary | O; M assigned; A view; W denied |
| GET /farms/{farm_id}/feed-stock/events | Paginated stock facts | O; M assigned; A view; W denied |
| POST /farms/{farm_id}/feed-stock/events | Opening/purchase/return/adjustment fact | O; M assigned |
| GET /expenses | Paginated expenses and filters | O; M assigned; A |
| POST /expenses | Record direct flock or farm-level expense | O; M assigned; A |
| PATCH /expenses/{expense_id} | Edit expense; audit and optimistic version | O; M assigned; A |
| GET /dashboard/operations | Operational summaries, gaps, mortality/FCR/alerts; includes computed_at/as_of and stale flag | O all; M assigned; W limited; A view-only operations |
| GET /dashboard/finance | Estimated/actual finance summaries; includes computed_at/as_of and stale flag | O; A |
| GET /reports/operations | Paginated operational report/export | O; M assigned; A view |
| GET /reports/finance | Paginated finance report/export | O; A |
| GET /alerts | List current in-app alerts | O; M assigned; A view; W limited to assigned flock alerts |
| GET /alert-rules | Read configured threshold rules | O; M assigned; A view |
| PUT /alert-rules/{farm_id} | Configure farm thresholds | O only until finer role permission is approved |
| POST /flocks/{flock_id}/close | Close flock after validation | O; M assigned |
| POST /flocks/{flock_id}/reopen | Reopen with mandatory reason; audit | O; SA (narrow administrative action only) |
| GET /audit-events | Paginated audit history with filters | O; M assigned view; A view |

## Explicit denial rules

- Worker cannot call finance, sales, payment, expense, report/export, feed-stock-value, user-management, close, or reopen routes.
- Accountant can read operational data but cannot create/edit operations. Finance access includes sales, payments, expenses, finance dashboard/reports.
- Super Admin cannot browse tenant business records. Tenant admin and reopen endpoints are narrow administrative exceptions. GET /auth/me returns only the Admin's own identity.
- Manager requests are rejected outside assigned farms, including reports with mixed farm IDs.
- Any route omitted above is denied by default; method access is checked separately from route access.

## MVP resource groups

auth, admin/tenants, users, farms, sheds, flocks, placements, daily-records, record-gaps, weight-samples, bird-transfers, buyers, sales, sale-payments, suppliers, feed-stock-events, expenses, dashboard, reports, alerts, alert-rules, audit-events.

## Dashboard freshness behavior

- If the latest projection is stale, return that last snapshot with its `computed_at` (`as_of`) and `is_stale: true`; never present it as current. If no snapshot exists, use an indexed bounded rebuild for the requested scope and return its computed time. Never fall back to an unbounded scan.

## Open design assumptions

- Invite-only onboarding was confirmed by the Phase 3 task; no public signup exists. Invitation delivery remains a deployment seam.
- The approved matrix says Accountant has finance view and operational read-only access. This outline makes Accountant finance summaries tenant-wide and operational records view-only; Manager scope remains assigned-farm.
- GET /tenant exposes only fields needed by authorized tenant users. Exact tenant settings are not a substitute for tenant_id request input.
- Roles for alert-threshold administration are not explicit in the approved matrix; only Owner may change rules until the owner assigns that action.
- Own, same day for Worker means own-created entry on the farm's current local date; role policy can adjust this without changing tenant rules.

## Phase 3 implemented identity subset

The implementation lives under `/api/v1/auth` and is intentionally limited to identity operations; the other endpoint rows remain design scope for later vertical slices.

| Method + path | Purpose | Permitted roles |
|---|---|---|
| POST `/auth/login` | Verify credentials, create refresh session, issue short-lived access token | Public; database rate-limited |
| POST `/auth/refresh` | Rotate the HttpOnly refresh cookie and issue a new access token | Valid refresh-session holder |
| POST `/auth/logout` | Revoke the presented refresh session and clear the cookie | Public operation scoped to the presented session cookie |
| POST `/auth/invitations/accept` | Set password and activate a single-use invitation | Public; valid, unexpired invitation token |
| POST `/auth/tenants` | Create tenant and initial Owner invitation | Super Admin |
| GET `/auth/tenants` | List tenant administration names and IDs | Super Admin |
| GET `/auth/users` | List users in the authenticated tenant | Owner |
| POST `/auth/invitations` | Invite a Manager, Worker, or Accountant | Owner |
| PATCH `/auth/users/{user_id}/role` | Change a tenant user's role and revoke their sessions | Owner; target must belong to the caller's tenant |
| GET `/health`, `/ready` | Process liveness and database readiness | Public; no business data |

## Phase 4 implemented farm operations endpoints

All rows below are tenant-scoped from the authenticated principal. Reads are paginated and accept `search` where relevant. Manager access is filtered to assigned farms.

| Method + path | Purpose | Permitted roles |
|---|---|---|
| GET, POST `/farms` | List/search; create | Owner, Manager, Worker, Accountant for GET; Owner for POST |
| GET, PATCH, DELETE `/farms/{farm_id}` | Read, edit, delete only when no sheds exist | GET: tenant roles; PATCH: Owner, assigned Manager; DELETE: Owner |
| GET, POST `/farms/{farm_id}/sheds` | List/search and create sheds | GET: tenant roles; POST: Owner, assigned Manager |
| PATCH, DELETE `/sheds/{shed_id}` | Edit; delete only when no flock exists | PATCH: Owner, assigned Manager; DELETE: Owner |
| GET, POST `/flocks` | List/search/filter and create a flock with its initial placement | GET: tenant roles; POST: Owner, assigned Manager |
| GET, PATCH, DELETE `/flocks/{flock_id}` | Read, rename active flock; delete only before placement | GET: tenant roles; PATCH: Owner, assigned Manager; DELETE: Owner |
| POST `/flocks/{flock_id}/placements` | Add placement fact | Owner, assigned Manager |
| POST `/flocks/{flock_id}/close` | Close and lock flock | Owner, assigned Manager |
| POST `/flocks/{flock_id}/reopen` | Reopen with reason; Super Admin lookup is limited to the specified flock and returns status only | Owner, Super Admin |
| GET, PUT `/settings` | Read/replace nullable bag size kg, target mortality percent, target FCR, and Manager/Worker daily edit windows (1–30 days; defaults 7/1) | Owner |

The PostgreSQL migration enforces one active flock per shed with a partial unique index; row-locking triggers enforce summed placement capacity and reject placement edits for closed flocks. Cross-table aggregate limits cannot be expressed as a regular CHECK constraint. API and domain validation return earlier, clearer errors, while database checks remain authoritative.

## Phase 6 implemented daily operations endpoints

All daily operations are scoped to the authenticated tenant and the flock's farm. Daily bird counts are calculated from placement and record facts in the domain engine; they are returned as derived values and are not stored.

| Method + path | Purpose | Permitted roles |
|---|---|---|
| GET, POST `/flocks/{flock_id}/daily-records` | List records and missing-day flags; submit a daily record with `Idempotency-Key` | GET: Owner, assigned Manager, Worker (own rows), Accountant; POST: Owner, assigned Manager, Worker (same day) |
| PATCH `/daily-records/{record_id}` | Edit with `expected_version`; recompute the ledger from the changed date and audit old/new values | Owner (any past date), assigned Manager (tenant-configured window, default 7 days), Worker (own record in tenant-configured window, default same day) |
| GET, POST `/flocks/{flock_id}/weight-samples` | Paginated list or add a sample size and average kg measurement | GET: Owner, assigned Manager, Worker (own rows), Accountant; POST: Owner, assigned Manager, Worker (same day) |
| GET, POST `/farms/{farm_id}/feed-purchases` | Paginated list or record feed purchases; bag input snapshots configured tenant bag size and normalized kg | GET: Owner, assigned Manager, Accountant; POST: Owner, assigned Manager |

Daily create uses unique `(tenant_id, flock_id, record_date)` and `(tenant_id, created_by, idempotency_key)` constraints. Matching request retries return the prior row; key reuse with different content conflicts. Updates require an expected version and append audit entries in the same transaction. The Owner configures the Manager and Worker date windows. See ADR 0007 for date-window, weekly-spacing, draft, and tap-count assumptions.
