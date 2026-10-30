# ADR 0001: Shared-schema tenant isolation

- Status: Accepted for Phase 3 implementation; RLS remains a production evaluation item
- Date: 2026-10-12

## Context

POUKTRY is a multi-tenant SaaS. Every business table must carry tenant_id, tenant identity comes only from authentication, repositories require tenant context, and cross-tenant tests are required. PostgreSQL Row-Level Security (RLS) must be evaluated as defense in depth.

## Options

1. Separate database per tenant.
2. Separate schema per tenant.
3. Shared schema with tenant_id and tenant-aware keys.
4. Shared schema with tenant_id plus PostgreSQL RLS.

## Decision

Choose shared schema and shared tables with non-null tenant_id on every tenant-owned record. Exempt only the tenants root table and platform identities (Super Admin user/session rows may have null tenant_id). Every tenant relationship uses composite (tenant_id, id) uniqueness and composite foreign keys. The server derives tenant scope from the authenticated principal; clients cannot select it. Every repository method requires a tenant context and includes it in reads/writes.

Evaluate RLS as an additional defense-in-depth control before production. If enabled, use transaction-local tenant context set after authentication, never a persistent connection setting. The application role must not bypass RLS. Super Admin tenant administration and flock reopening use narrow privileged service paths; there is no general Super Admin business-data query path.

## Consequences

- One migration stream and pooled database are simpler for the initial SaaS.
- Query filters and tenant-aware FKs must be consistent; a missing filter remains a risk, so test each endpoint/role and cross-tenant ID attempt.
- RLS can contain repository mistakes, but does not replace application authorization. Connection pool reset and transaction-local scope require integration tests.
- Tenant database separation remains an option if regulatory, scale, or customer isolation needs change; revisit with evidence and an ADR.
