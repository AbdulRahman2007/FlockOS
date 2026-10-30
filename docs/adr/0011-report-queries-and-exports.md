# ADR 0011: Paginated reports and exports

## Context

Phase 9 needs tenant and role scoped flock, mortality, feed, weight, financial, and profitability reports. Reports must support date and farm/flock filters, pagination, CSV/PDF output, and large exports without building the full CSV in server memory.

## Decision

- Report reads require `reports:read`; every query filters by the authenticated tenant. Managers are additionally limited to assigned farms. Worker and Super Admin roles have no report permission.
- JSON reports use server-side `limit`/`offset` pagination. CSV responses stream successive 500-row pages and never assemble the full CSV in memory.
- Mortality uses the approved period formula (deaths divided by birds alive at period start). When a flock has no valid opening count, the report returns a null percentage and status instead of inventing a denominator.
- Flock counts are derived through the report end date from placement, death, culling, and sale facts. The flock report includes active flocks placed during the selected interval so its live-bird total can be reconciled to the dashboard for that scope.
- Profitability rows reuse the existing approved flock-profit calculation as of the selected end date. The start date selects flocks placed during the interval; profit remains cumulative through the end date.
- Financial rows show sales, receipts, expenses, and feed purchases as distinct fact types. The report does not combine feed-purchase amounts with expense totals or recalculate profit.
- PDF export uses a full report print view and the browser's Save as PDF flow. The report table is print styled; no server PDF renderer is added.

## Consequences

Report filters and formulas remain tied to persisted facts and existing domain calculations. CSV delivery is bounded in server memory by page size. PDF rendering uses the browser's print engine. A numeric 10,000-row export budget is set by the product owner at 10 seconds and 64 MB peak additional memory for the Phase 9 exit check.
