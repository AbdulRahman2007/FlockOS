# Formula register and golden case outline

Status: Core worked examples and the FCR/profit definitions below were approved by the product owner on 2026-10-12. Confirmed edge-case rules F1–F6 below resolve the previously open bird-ledger, mortality, weight/FCR as-of, and buyer-credit cases. Use exact decimal arithmetic and fixed precision in implementation.

## 1. Remaining birds (D2)

**Decision formula:** `remaining = placed - mortality - culling - sold - transferred_out + transferred_in`.

**Worked example:** Start with 5,000 placed birds. Record 30 deaths, 5 culled, 100 sold, 20 transferred out, and 10 transferred in. `5,000 - 30 - 5 - 100 - 20 + 10 = 4,855 birds remaining`.

**Transfer status (T1):** bird transfers are deferred to v1.1. The ledger formula remains reserved. Until then, live dashboard totals exclude transfers. When transfers are added, represent them as paired transfer-out and transfer-in events; transfers in count in the destination flock's opening birds for that date.

## 2. Mortality and total loss (D5)

**Cumulative mortality %:** `cumulative deaths / placed birds × 100`.

**Daily or weekly mortality %:** `deaths in period / birds alive at period start × 100`.

**Total loss count:** `deaths + culling`; D5 says culling is tracked separately but included in total loss. Mortality percentage remains deaths-only.

**Worked example:** A flock placed 5,000; cumulative deaths are 40, so `40 / 5,000 × 100 = 0.8%`. If 4,900 birds were alive at the start of a week and 14 die in it, weekly mortality is `14 / 4,900 × 100 ˜ 0.2857%`. If 6 birds were culled that week, total losses for the week are `14 + 6 = 20 birds` (not 20 deaths).

**Period and ordering rule (F1/F2):** the denominator is the opening birds of the first day in the period. Within each day, apply mortality, culling, transfers out (reserved), and then sales at end of day. Same-day sales do not change that day's mortality denominator. Culling is excluded from mortality percentage and included in total loss.

## 3. Running and final raw FCR (D6)

**Approved common structure:** `FCR = cumulative feed consumed (kg) / net live-weight gain (kg)`.

**Approved running denominator:** `unsold closing live biomass + cumulative sold live weight + cumulative dead- and culled-bird biomass - placement biomass`. Unsold closing live biomass uses closing birds × the average weight for the selected as-of day. Transfers are not part of FCR in v1.

**Approved final denominator:** `total sold live weight + cumulative dead- and culled-bird biomass - placement biomass`. Closed flocks use final FCR based on total sold weight. Transfers are not part of FCR in v1.

**Worked running example:** 12,000 kg feed; 4,000 birds alive at 1.2 kg average (= 4,800 kg); 500 kg sold live weight; 120 kg recorded dead-bird biomass; 500 kg placement biomass (5,000 chicks × 0.1 kg). Net gain is `4,800 + 500 + 120 - 500 = 4,920 kg`; running FCR is `12,000 / 4,920 ˜ 2.439`.

**Worked final example:** 14,000 kg feed; 6,200 kg total sold live weight; 150 kg recorded dead-bird biomass; 500 kg placement biomass. Net gain is `6,200 + 150 - 500 = 5,850 kg`; final FCR is `14,000 / 5,850 ˜ 2.393`.

**Weight sampling and as-of rules (F3/F5):** interpolate linearly between sampled weights, using placement weight as day 0. After the last sample, carry that sample forward and flag the figure as estimated. If no weight sample exists, FCR is unavailable (`null`), never zero. Use only facts dated on or before the selected as-of date. A backdated entry recomputes everything after its date.

## 4. Feed stock (D7)

**Stock in kg:** `opening stock + purchases - usage + returns_to_stock ± adjustments` (returns into stock add; use signed adjustments: positive adds, negative removes).

**Bag conversion:** `quantity in bags × configured kg per bag = quantity in kg`.

**Worked example (approved):** Opening 1,000 kg + 20 bags × 50 kg/bag (=1,000 kg) - 700 kg used + 25 kg returned into stock + 10 kg adjustment = `1,335 kg`.

## 5. Estimated and actual profit (D8)

D8 specifies separation and cost allocation, but not all report conventions. The product owner approved the revenue-minus-cost structure and bird-days allocation below.

**Approved direct/farm cost allocation:** `farm cost allocated to flock = farm-level cost × (flock birds × flock days) / sum across eligible flocks (birds × days)`. Each farm expense selects its eligible flocks and inclusive farm-local date interval (ADR 0010). Bird-days are the sum of each included day's opening live count; same-day mortality, culling, and sales affect the following day's bird-days.

**Approved estimated profit:** `current live biomass × latest applicable entered market price - direct costs - allocated farm costs`, where `current live biomass = birds alive × latest average weight` and entered market price is PKR/kg. The market-price event is effective-dated; the newest applicable event is used for the selected estimate date.

**Approved actual profit:** `recorded sales amount - direct costs - allocated farm costs`; cash received remains a separate measure. Actual profit uses recorded sales amounts, not payments collected.

**Phase 8 implementation convention (ADR 0010):** each farm expense selects its eligible flocks and an inclusive farm-local date interval. Bird-days are derived from the daily ledger as the sum of each included day's opening live count. Same-day mortality, culling, and sales affect the following day's bird-days. Profit reports recalculate allocations from these facts, so backdated ledger edits flow through without a stale stored total. No default eligible set or interval is assumed.

**Worked allocation example (approved):** Two eligible flocks in a month have 100 birds × 10 days = 1,000 bird-days and 50 × 10 = 500 bird-days. A PKR 15,000 shared farm cost allocates PKR `15,000 × 1,000 / 1,500 = 10,000` to flock A and PKR 5,000 to flock B.

**Worked estimated/actual illustration (approved):** If 1,000 birds are alive and the latest average weight is 1 kg, current live biomass is `1,000 × 1 = 1,000 kg`. At an entered market price of PKR 300/kg, estimated revenue is PKR 300,000. With PKR 180,000 direct costs and PKR 10,000 allocated costs, estimated profit is PKR 110,000. If actual recorded sales are PKR 280,000 with those same costs, actual profit is PKR 90,000. If PKR 200,000 has been paid, cash received is not the actual-profit revenue under this definition.

## 6. Sales outstanding (D12)

**Outstanding by buyer:** `sum(sales amounts) - sum(payments received)`.

**Worked example (approved):** Buyer has two sales of PKR 120,000 and PKR 80,000, and payments of PKR 100,000 and PKR 25,000. Outstanding is `120,000 + 80,000 - 100,000 - 25,000 = PKR 75,000`.

**Credit and sale amount rule (F6):** payments remain separate events. Sale amount is stored independently of weight × rate. Negative buyer balances are displayed as `Credit in favour of buyer`; they do not auto-settle in v1. Dashboard outstanding sums only positive buyer balances and shows credits separately.

**Phase 8 implementation note (ADR 0009):** receipts are separate tenant-scoped events and sale amount is stored independently from weight × rate. Apply F6 when presenting buyer balances and dashboard totals.

## Confirmed worked examples (F1–F6)

The following rules and worked examples are confirmed product-wide. Keep each worked example exactly as written when implementing or updating this register.

### F1 — Within-day bird order and closing count

Order within a day: opening birds, then mortality, culling, transfers out (reserved), then sales at end of day.
   closing = opening - mortality - culling - transfers out + transfers in - sold.
   Example: opening 1,000; mortality 5; culling 2; sold 300 -> closing 693. Daily mortality % = 5 / 1,000 = 0.5000%.

### F2 — Period and cumulative mortality

Period mortality % = deaths in the period / birds alive at the START of the period (opening birds of the first day). Same-day sales happen at end of day, so they never change that day's denominator. Culling is excluded from mortality % but included in total loss.
   Example: week starts with 4,900 birds alive; 21 deaths in the week -> 21 / 4,900 = 0.4286%. Cumulative: 149 deaths / 5,000 placed = 2.9800%.

### F3 — Average weight and unavailable FCR

Average weight on any day: linear interpolation between sampled weights, with the placement weight as day 0. After the last sample, carry the last sample forward (no extrapolation) and flag the figure as estimated. If no weight sample exists yet, FCR is 'unavailable' (null), never 0.
   Example: samples day 7 = 0.185 kg and day 14 = 0.465 kg. Day 10 = 0.185 + (0.465 - 0.185) x 3/7 = 0.305 kg.

### F4 — Weight gain and running FCR biomass

Dead and culled birds count in the weight gain at that day's average weight (F3). Unsold closing birds count at closing birds x average weight. Transfers are not part of FCR in v1.
   Example: placed 1,000 at 0.040 kg; day 14 closing 985 birds; average weight 0.465; cumulative dead/culled weight 3.000 kg; sold 0; cumulative feed 600 kg.
   Live weight = 985 x 0.465 = 458.025. Gain = 458.025 + 0 + 3.000 - (1,000 x 0.040 = 40.000) = 421.025 kg. FCR = 600 / 421.025 = 1.425.

### F5 — As-of date and closed-flock FCR

As-of date: use only facts dated on or before it. A backdated entry recomputes everything after its date. Closed flocks use the final FCR (total sold weight).

### F6 — Buyer balance and dashboard outstanding

Buyer balance = sales - payments. If negative, display 'Credit in favour of buyer', no auto-settlement in v1. The dashboard outstanding total sums only positive balances; credits are shown separately.
   Example: sales 100,000; payments 120,000 -> balance -20,000 -> shown as 'Credit in favour of buyer: PKR 20,000'; it does not reduce other buyers' outstanding.

## Golden case outline: 5,000 broilers over 35 days

- Store a versioned, human-readable fixture and its hand-calculated spreadsheet/source reference. Do not invent expected results from the implementation.
- The approved synthetic candidate records 5,000 placed chicks over 35 daily rows, weekly weight samples, partial sales, feed movements, and costs. It has no missed day, so gap handling is not covered by this fixture.
- Include explicit placement weight, dead-bird weights, sample sizes/average weights, bag conversion, sale weight/rate/payments, direct costs, shared costs, and any transfer events used by formulas.
- Spreadsheet independently calculates every daily closing bird count, mortality measures, running/final FCR, feed stock, allocated costs, estimated/actual profit, and buyer outstanding. Each expected value has units and stated rounding.
- Domain engine must match the approved spreadsheet exactly for the chosen precision. Add boundary/property cases separately; the golden fixture is a fixed regression case.
- **Approved for Phase 5 candidate regression (2026-10-23):** the owner approved the supplied synthetic inputs, assumptions A1-A9, and corrected expected outputs documented below. The candidate remains synthetic and is not a real-farm dataset.

## Phase 5 implementation and rounding

- The pure calculation module accepts `Decimal` weights, feed quantities, and PKR values; binary floating point is never used in arithmetic.
- No value is quantized during calculation or for display. Non-terminating divisions (mortality percentages, FCR, bag equivalents, and cost allocation) use Python Decimal's standard 28-significant-digit context (`ROUND_HALF_EVEN` by default); this is calculation precision, not a display format.
- Bird counts remain integers and are never rounded. Daily facts are aggregated by local date before ledger calculation; the ledger applies all movements for that date together and checks that the resulting closing count is non-negative.
- Approved: retain full Decimal precision in domain calculations and round PKR only when storing it at two decimal places. The calculation functions return their Decimal result without quantizing it. The tie-breaking rounding mode at the persistence boundary must match the database behavior and be tested there.
- Percent and FCR output display precision is also not defined; callers must not round the domain result in a way that changes downstream calculations.

The synthetic 35-day candidate is stored at `backend/tests/fixtures/golden_5000_broiler_candidate.json`. The owner approved the following assumptions and corrected expected outputs for this candidate on 2026-10-23. They apply to this fixture and do not change `docs/decisions.md` or establish new product-wide rules.

### Candidate assumptions A1–A9 (owner-approved for this fixture)

- **A1 — Lost-bird biomass:** estimate the day's dead and culled bird weight using that day's flock average weight. Use linear interpolation between the neighboring weekly samples; do not extrapolate outside the sample ages. Deaths and culls use the same estimated average weight.
- **A2 — Sample meaning:** each sample's average weight represents the flock average at its stated age; sample size is recorded metadata and does not alter the average. Day 0 is the placement-weight sample.
- **A3 — Mortality units and period start:** expose mortality as percentage points (`deaths / denominator × 100`), not a unit fraction. Daily denominator is birds alive at the start of that day, before that day's mortality, culling, or sale. Culling contributes to total loss but not mortality.
- **A4 — Daily movement and bird-days:** aggregate all same-day bird movements for closing counts. Bird-days are the sum of birds alive at the start of each included production day; same-day losses and sales reduce the following day's bird-days.
- **A5 — Feed stock timing and returns:** apply that day's purchases, returns, and adjustments before that day's feed usage. The `Return` event category means feed returned into farm stock, so the fixture's signed `-100 kg` is normalized to `+100 kg`; adjustment signs are used as supplied.
- **A6 — Sales amount:** for this synthetic case only, sale amount is total live weight × entered rate per kg. Payments remain separate; outstanding is sale amounts minus payments.
- **A7 — Direct costs and allocation:** value feed consumed at the input feed-bag price divided by configured bag size; chick cost is placement count × chick price. Treat listed expenses as direct flock costs. Allocate the farm pool by eligible bird-days, using the supplied other-flock bird-days for the same allocation interval.
- **A8 — Decimal and output rounding:** use Decimal with the standard 28-digit, half-even context; never round intermediate calculations. The candidate's strings are spreadsheet display values, so the regression rounds only the final result to the number of decimal places printed in that expected string, half-even. At a PKR persistence boundary, round to two decimal places, half-up.
- **A9 — Profit cutoff:** at day 28, estimated profit is current live biomass × entered market price minus chick cost, feed consumed to date, flock expenses dated through day 28, and the allocated share of the full supplied farm pool. Assume the supplied pool is fully incurred by that checkpoint because no pool timing is given. At flock close, actual profit is derived sale revenue minus total direct and allocated costs; payments do not change profit.

Under A3, expected mortality values in the source are multiplied by 100 because they are stored as fractions. The source G-16 expected value is inconsistent with its displayed G-13 + G-14 - G-15 values at the last shown digit; the regression uses the A1-derived value (9647.33571428571 kg). Under A5, feed-stock checkpoints on/after the day-31 return are 200 kg higher than the source outputs, which subtracted the signed return. Under A9, estimated-profit output includes allocated farm cost as required by D8. The test records these corrections explicitly. The fixture has a record for every day, so it does not exercise missing-day gap behavior.

The candidate regression applies the approved corrections above to conflicting source expected values. The fixture contains all 35 daily records and therefore does not exercise missing-day gap behavior. Keep the original pasted source for provenance; this approved candidate remains synthetic and must not be represented as a real-farm dataset.
