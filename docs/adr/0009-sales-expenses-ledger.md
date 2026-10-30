# ADR 0009: Sales and expense facts

## Context

Phase 8 requires partial sales to reduce derived flock counts, separate receipts to support buyer balances, suppliers and expenses to be tenant scoped, and edits to be auditable. D12 defines buyer outstanding as recorded sales less received payments. D8 approves bird-days allocation but leaves eligible flocks, bird-count basis, and allocation period unspecified.

## Decision

- Store each sale and receipt as separate tenant-scoped facts. A sale records birds, live weight, rate, and amount independently; the API does not impose amount = weight × rate.
- Include sale bird movements in the same daily bird ledger used by daily record validation. Serialize sale creation on the flock row and reject a sale that makes any closing count negative.
- Store expenses in a unified `expenses` table with direct-flock and farm scope. Preserve prior direct-cost rows in the migration.
- Record sale, payment, and expense creation in the audit log. Payments remain separate from actual profit revenue.
- Calculate outstanding as raw sales minus payments; a negative result is retained as a buyer credit pending a product decision on overpayments.
- At the initial Phase 8 slice, shared farm-cost allocation remained unavailable. ADR 0010 supersedes that temporary limitation by requiring an explicit eligible flock set and date interval per farm expense.

## Consequences

Sales and receipts are independently traceable and sales affect the live-bird ledger. Existing direct-cost data survives the table rename. Sale and expense updates use optimistic versions and audit old/new values. A sale edit rebuilds and validates the affected bird ledger before commit; a stale version or negative closing count is rejected.
