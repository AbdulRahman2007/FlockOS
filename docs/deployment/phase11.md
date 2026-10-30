# Phase 11: Deployment and operations

## Current status

Phase 11 is **in progress**. This repository now contains production-oriented API and frontend container definitions, a CI image-build job, production endpoint validation, a tenant/Owner-invitation operator script, and a staging uptime check with a webhook alert test. GitHub Actions CI already upgrades a disposable PostgreSQL database with Alembic before running backend tests.

The live deployment gates remain open. Per P5 in `docs/decisions.md`, the managed PostgreSQL provider is not selected and must not be selected by implementation. No cloud resources, staging environment, production environment, custom domain, provider secret store, automated database backups, restore rehearsal, deployed-image rollback, or hosted error-tracking service are configured or verified here.

## Container images

Build from the repository root:

```powershell
docker build -f Dockerfile.api -t pouktry-api:local .
docker build -f Dockerfile.frontend --build-arg VITE_API_URL=https://api.example.invalid/api/v1 -t pouktry-frontend:local .
```

The frontend build argument is public configuration, not a secret. The API image runs as a non-root user, has a liveness health check, and does not run migrations during startup. The frontend image serves the SPA as a non-root user on port 8080 and applies basic security headers. The target provider's TLS edge must provide HTTPS and HSTS. CI builds both images without publishing them.

## Runtime settings and secret handling

Set values through the selected hosting provider's secret/configuration store, never in source control, image build arguments, or deployment logs.

| Setting | Kind | Purpose |
|---|---|---|
| `APP_ENVIRONMENT=production` | Config | Enables production startup validation |
| `DATABASE_URL` | Secret | Managed PostgreSQL connection; SQLAlchemy `postgresql+psycopg` URL with TLS `sslmode` (`require`, `verify-ca`, or `verify-full`) |
| `JWT_SECRET` | Secret | Unique randomly generated signing key; rotate the exposed bootstrap credential before production use |
| `FRONTEND_ORIGIN` | Config | Exact HTTPS origin allowed by API CORS |
| `VITE_API_URL` | Public build config | HTTPS API URL ending in `/api/v1`; bake it into each environment's frontend image |
| `STAGING_BASE_URL` | CI variable | Staging API origin used by the scheduled health check |
| `UPTIME_ALERT_WEBHOOK` | Secret | HTTPS webhook accepting a JSON `{ "text": "..." }` alert |

Use separate runtime and migration database roles. The runtime role should not have schema DDL privileges. Give the migration job its own least-privilege credential. The provider must document TLS verification, network allowlists, backup retention, restore procedure, and its incident process before storing real client data.

## Migrations and deployment pipeline

The existing `CI` workflow applies all Alembic migrations to an isolated PostgreSQL service on every eligible CI run, then runs the backend tests. The added `container-images` job builds both Dockerfiles after those backend and frontend checks. It does not publish images or deploy them.

After selecting a hosting provider, extend the main-branch pipeline in this order:

1. Build and publish immutable API and frontend image digests.
2. Require CI and image-build success.
3. Take/verify the provider backup required by its migration policy.
4. Run `alembic -c backend/alembic.ini upgrade head` once as a release job using the migration role; do not run migrations from every API replica.
5. Deploy the same immutable digests to staging, wait for `/health` and `/ready`, and run real-backend smoke tests.
6. Require a protected production environment approval, then deploy those digests to production and verify health/readiness.

Provider-specific deploy commands, image registry, protected environment rules, and production approvals cannot be wired until the hosting choice is made. Do not put a production database URL into pull-request CI.

## Staging, uptime alerts, and error tracking

Configure a staging API and frontend with separate database, signing key, origin, and domain from production. Add `STAGING_BASE_URL` as a GitHub Actions variable and `UPTIME_ALERT_WEBHOOK` as a GitHub Actions secret. The scheduled `Staging uptime` workflow checks both `/health` and `/ready` every ten minutes. Use its manual `simulate_failure` input to send a test notification without failing the workflow when the webhook acknowledges it. The health checker never prints the webhook URL or response body.

The application returns generic 500 responses and logs an error type and request ID, with no request body or authorization headers. A hosted error-tracking service and its data-retention/access policy are not selected or configured; this remains an exit gate. Configure it to omit request bodies, cookies, authorization headers, and local variables before sending exceptions.

## Tenant provisioning

From PowerShell, use the Super Admin access token when prompted; do not place it in command arguments or shell history:

```powershell
.\scripts\Provision-Tenant.ps1 `
  -ApiBaseUri 'https://api.example.invalid/api/v1' `
  -TenantName 'Example Poultry' `
  -OwnerEmail 'owner@example.invalid' `
  -OwnerName 'Farm Owner'
```

The script calls the existing audited Super Admin tenant-creation endpoint. It stores the one-time Owner invite response in a current-user-only directory under `%LOCALAPPDATA%`, outside the OneDrive repository. Deliver the token through an approved secure channel, then remove the file after acceptance. If the request fails after the server may have committed, inspect tenant state before retrying to avoid duplicate provisioning.

## Backups, restore drill, and rollback

The required daily managed-PostgreSQL backups and a tested restore are not configured until a provider is selected. The owner must set retention and recovery-point/recovery-time objectives with that provider; this document does not invent them.

Restore drill, once the provider exists:

1. Select a recent automated backup and record its timestamp and source database identifier.
2. Restore it into a **fresh isolated database**, not over staging or production.
3. Apply only forward migrations needed for the deployed image.
4. Verify Alembic's current revision, readiness, tenant separation, and representative farm/flock/daily/finance records against recorded expectations.
5. Record duration, data-loss window, operator, and evidence; delete the isolated database after approval.

Rollback procedure:

1. Stop the rollout and record the failed release/image digests and migration revision.
2. Roll API and frontend back to their previous immutable image digests.
3. Keep the database on its current revision when the previous application is compatible. Migrations must use expand-and-contract changes; do not run `alembic downgrade` as an automatic rollback.
4. If data/schema recovery is necessary, restore the selected backup into a fresh database, verify it, then switch the connection only through the provider's reviewed procedure. Preserve the original database read-only until recovery is accepted.
5. Confirm `/health`, `/ready`, authentication, and a tenant-scoped read/write smoke check; communicate the incident through the configured channel.

This rollback is a documented procedure only; it has not been rehearsed against a provider. Phase 11 exit requires the staging-to-production deploy, fresh-database restore, rollback rehearsal, and alert test to complete with retained evidence.
