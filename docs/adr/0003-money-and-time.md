# ADR 0003: Money facts and farm-local dates

- Status: Proposed for review
- Date: 2026-10-12

## Context

Finance figures must remain exact PKR values. Sales can be partial, payments are separate facts, outstanding is sales less payments per buyer, and estimated profit must remain separate from actual profit. Farm-local operational dates use Asia/Karachi while timestamps are UTC.

## Options

1. Store money as floating point and store all dates as UTC timestamps.
2. Store decimal money and UTC timestamps, but derive farm-local dates at query time.
3. Store exact decimal money, UTC timestamps, and explicit farm-local date facts; keep payment/cost facts separate.

## Decision

Choose option 3. Use NUMERIC(14,2) for PKR amounts and never binary floating point. Store timestamps as timestamptz UTC. Store daily-record, placement, sample, sale, expense, and stock-event business dates as PostgreSQL date values in the farm's configured timezone (Asia/Karachi by default). Record actor time separately in UTC.

A sale stores bird count, total live weight, rate per kg, and entered amount as distinct facts. Do not force amount = weight × rate until the owner approves rounding/override behavior. Payments are separate positive payment facts. Buyer outstanding is derived from sales amounts minus payment facts. Expenses are separate direct-flock or farm-level cost facts. Estimated and actual profit use separate labelled calculations. Farm-level costs use the approved configurable birds × days allocation family; denominator scope and exact bird-count basis remain explicit inputs, not hidden constants.

## Consequences

- Decimal scale and currency are stable across persistence/API; API serializes decimal values losslessly.
- The database stores both occurrence date and UTC audit timestamps, avoiding midnight ambiguity for shed workers and cross-timezone reports.
- Date filters must use a farm's timezone and indexed date columns, not cast UTC timestamps in a way that defeats indexes.
- Payment, sales amount, and profit remain reconcilable but are not conflated with cash collected.
- Configurable allocation methods and estimated-revenue basis need documented configuration and approval before implementation.
