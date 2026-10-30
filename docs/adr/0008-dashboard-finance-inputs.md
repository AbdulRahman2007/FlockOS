# ADR 0008: Minimum dashboard finance facts

- Status: Accepted for the current dashboard slice
- Date: 2026-10-26

## Context

Estimated profit needs an effective-dated market price and flock direct-cost facts. The existing model had neither. D8's shared farm-cost allocation still lacks an eligible flock set and allocation period. The owner directed this slice to show direct costs only and defer farm-cost allocation.

## Decision

Add tenant- and farm-scoped effective market-price events and tenant-, farm-, and flock-scoped direct-cost events. Store PKR as `NUMERIC(14,2)`, retain effective/incurred local dates, and audit creation. Any estimated-profit value from this slice must be labelled as excluding shared farm costs. Do not claim it is the complete D8 estimate.

## Consequences

- Finance facts are normalized and tenant-scoped; direct costs cannot point to a flock from another farm or tenant.
- Shared farm-cost allocation and actual profit remain unavailable until their product rules and sales facts are implemented.
- The dashboard read path, query plans, and latency still need implementation and measurement on seeded realistic data. If snapshots are introduced, they must remain rebuildable from source facts as described in ADR 0005.
