# ADR 0013: Provider-neutral Phase 11 deployment artifacts

- Status: Accepted for repository implementation; hosted rollout pending provider selection
- Date: 2026-10-31

## Context

Phase 11 requires production containers, migrations in the release pipeline, staging and production, HTTPS, managed PostgreSQL backups, a tested restore, uptime/error tracking, tenant provisioning, and rehearsed rollback. Decision P5 in `docs/decisions.md` explicitly says the managed PostgreSQL provider is not chosen and must not be selected by implementation. No production hosting account or custom domain is configured in this repository.

## Options

1. Select a cloud/database provider and wire its deployment now.
2. Add portable images and operational scripts, document required secret/configuration contracts, and defer provider-bound deployment until selection.
3. Leave Phase 11 unchanged until all provider decisions are made.

## Decision

Use option 2. Build API and static frontend OCI images; run migrations as a single release job, not in API startup; build images in CI without publishing; use GitHub Actions for scheduled staging health/readiness checks and a generic HTTPS JSON webhook alert. Provide an operator-driven tenant/Owner-invite script that keeps the token outside the synced repository.

Do not choose a managed database, hosting provider, registry, custom domain, or error-tracking service here. Do not claim a cloud deployment, backup, restore, rollback, or alert rehearsal has passed until it runs against configured infrastructure and its evidence is recorded.

## Consequences

- CI verifies migrations on disposable PostgreSQL and builds both images after quality checks.
- Production startup rejects the development signing key, local database URLs, non-TLS PostgreSQL URLs, and non-HTTPS frontend origins.
- Provider-specific staging/production deployment, managed backups, restore, rollback rehearsal, and hosted error tracking remain release gates.
- The uptime workflow requires a staging API origin and a webhook accepting a JSON `text` field.
