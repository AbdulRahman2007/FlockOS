# ADR 0010: Per-expense eligible flocks and bird-day period

## Context

D8 approves farm expense allocation by flock bird-days, but leaves the eligible flock set and allocation period unspecified. Blocking all allocation leaves the flock profit view incomplete; silently using every flock or an assumed cycle would misstate costs.

## Decision

- Each farm-level expense records its own allocation start date, end date, and eligible flock set. This makes the unresolved choices explicit at entry rather than imposing one farm-wide convention.
- Dates are farm-local business dates and the configured interval is inclusive. Bird-days sum the live flock count at the start of each included day; that day's deaths, culling, and sales affect the following day's count.
- Derive bird-days from placement, daily records, and sales facts when calculating flock profit. Do not persist a non-rebuildable allocation total.
- Allocate each farm expense by `expense amount × flock bird-days / total selected eligible bird-days`. A farm expense without eligible bird-days contributes no allocated amount and is surfaced as an invalid configuration by validation/report status.
- Link suppliers to feed purchases and expenses with tenant-scoped foreign keys.

## Consequences

Owners, managers, and accountants must choose the eligible flock set and interval for each shared expense. Profit results are reproducible from ledger facts plus the recorded configuration, and backdated daily edits change recalculated allocations. This does not establish a default eligible set or allocation interval for future expenses.
