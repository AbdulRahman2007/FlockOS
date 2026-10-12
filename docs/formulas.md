# Formula register and golden case outline

Status: Core worked examples and the FCR/profit definitions below were approved by the product owner on 2026-10-12. Values are illustrative and approved. Use exact decimal arithmetic and fixed precision in implementation. Remaining edge-case interpretations are called out per formula and need resolution before implementation.

## 1. Remaining birds (D2)

**Decision formula:** `remaining = placed - mortality - culling - sold - transferred_out + transferred_in`.

**Worked example:** Start with 5,000 placed birds. Record 30 deaths, 5 culled, 100 sold, 20 transferred out, and 10 transferred in. `5,000 - 30 - 5 - 100 - 20 + 10 = 4,855 birds remaining`.

**Still to define:** how transfer events are represented between flocks without double counting. The worked arithmetic is approved.

## 2. Mortality and total loss (D5)

**Cumulative mortality %:** `cumulative deaths / placed birds × 100`.

**Daily or weekly mortality %:** `deaths in period / birds alive at period start × 100`.

**Total loss count:** `deaths + culling`; D5 says culling is tracked separately but included in total loss. Mortality percentage remains deaths-only.

**Worked example:** A flock placed 5,000; cumulative deaths are 40, so `40 / 5,000 × 100 = 0.8%`. If 4,900 birds were alive at the start of a week and 14 die in it, weekly mortality is `14 / 4,900 × 100 ≈ 0.2857%`. If 6 birds were culled that week, total losses for the week are `14 + 6 = 20 birds` (not 20 deaths).

**Still to define:** period-start live-count handling for same-day placement, transfers, or sales and display precision. The worked arithmetic is approved.

## 3. Running and final raw FCR (D6)

**Approved common structure:** `FCR = cumulative feed consumed (kg) / net live-weight gain (kg)`.

**Approved running denominator:** `current live biomass + cumulative sold live weight + recorded dead-bird biomass - placement biomass`. Current live biomass uses latest sampled average weight × birds alive, as D6 requires.

**Approved final denominator:** `total sold live weight + recorded dead-bird biomass - placement biomass`, following “final FCR uses total sold live weight,” including dead-bird weight and subtracting placement weight. This assumes flock close/final calculation after all sale weight is recorded.

**Worked running example:** 12,000 kg feed; 4,000 birds alive at 1.2 kg average (= 4,800 kg); 500 kg sold live weight; 120 kg recorded dead-bird biomass; 500 kg placement biomass (5,000 chicks × 0.1 kg). Net gain is `4,800 + 500 + 120 - 500 = 4,920 kg`; running FCR is `12,000 / 4,920 ≈ 2.439`.

**Worked final example:** 14,000 kg feed; 6,200 kg total sold live weight; 150 kg recorded dead-bird biomass; 500 kg placement biomass. Net gain is `6,200 + 150 - 500 = 5,850 kg`; final FCR is `14,000 / 5,850 ≈ 2.393`.

**Owner-approved formula; edge cases remain:** The approved worked denominator includes current biomass, sold live weight, recorded dead-bird biomass, and placement biomass as shown. Culls, transfers, unsold closing biomass at finalization, missing dead-bird weights, partial-sale weights, and feed/weight cut-off dates still need rules before implementation. The example assumes recorded dead weight and excludes culls/transfers.

## 4. Feed stock (D7)

**Stock in kg:** `opening stock + purchases - usage + returns_to_stock ± adjustments` (returns into stock add; use signed adjustments: positive adds, negative removes).

**Bag conversion:** `quantity in bags × configured kg per bag = quantity in kg`.

**Worked example (approved):** Opening 1,000 kg + 20 bags × 50 kg/bag (=1,000 kg) - 700 kg used + 25 kg returned into stock + 10 kg adjustment = `1,335 kg`.

## 5. Estimated and actual profit (D8)

D8 specifies separation and cost allocation, but not all report conventions. The product owner approved the revenue-minus-cost structure and bird-days allocation below.

**Approved direct/farm cost allocation:** `farm cost allocated to flock = farm-level cost × (flock birds × flock days) / sum across eligible flocks (birds × days)`. Eligible flock set, bird-count basis, and allocation period remain to be specified; do not invent them in code.

**Approved estimated profit:** `current live biomass × latest applicable entered market price - direct costs - allocated farm costs`, where `current live biomass = birds alive × latest average weight` and entered market price is PKR/kg. The market-price event is effective-dated; the newest applicable event is used for the selected estimate date.

**Approved actual profit:** `recorded sales amount - direct costs - allocated farm costs`; cash received remains a separate measure. Actual profit uses recorded sales amounts, not payments collected.

**Worked allocation example (approved):** Two eligible flocks in a month have 100 birds × 10 days = 1,000 bird-days and 50 × 10 = 500 bird-days. A PKR 15,000 shared farm cost allocates PKR `15,000 × 1,000 / 1,500 = 10,000` to flock A and PKR 5,000 to flock B.

**Worked estimated/actual illustration (approved):** If 1,000 birds are alive and the latest average weight is 1 kg, current live biomass is `1,000 × 1 = 1,000 kg`. At an entered market price of PKR 300/kg, estimated revenue is PKR 300,000. With PKR 180,000 direct costs and PKR 10,000 allocated costs, estimated profit is PKR 110,000. If actual recorded sales are PKR 280,000 with those same costs, actual profit is PKR 90,000. If PKR 200,000 has been paid, cash received is not the actual-profit revenue under this definition.

## 6. Sales outstanding (D12)

**Outstanding by buyer:** `sum(sales amounts) - sum(payments received)`.

**Worked example (approved):** Buyer has two sales of PKR 120,000 and PKR 80,000, and payments of PKR 100,000 and PKR 25,000. Outstanding is `120,000 + 80,000 - 100,000 - 25,000 = PKR 75,000`.

**Still to define:** payment event/aggregate representation, overpayments or credit balances, and whether sales amount must equal weight × rate or may be separately entered.

## Golden case outline: 5,000 broilers over 35 days

- Store a versioned, human-readable fixture and its hand-calculated spreadsheet/source reference. Do not invent expected results from the implementation.
- Begin with 5,000 placed chicks; record farm-local dates for 35 days and daily facts for deaths, culling, feed used, water, temperature, and notes. Include at least one missed day (expected flagged gap, no zero record), a weekly weight sample, a partial sale, and stock purchases/returns/adjustments only after the owner agrees exact case values.
- Include explicit placement weight, dead-bird weights, sample sizes/average weights, bag conversion, sale weight/rate/payments, direct costs, shared costs, and any transfer events used by formulas.
- Spreadsheet independently calculates every daily closing bird count, mortality measures, running/final FCR, feed stock, allocated costs, estimated/actual profit, and buyer outstanding. Each expected value has units and stated rounding.
- Domain engine must match the approved spreadsheet exactly for the chosen precision. Add boundary/property cases separately; the golden fixture is a fixed regression case.
- **Pending:** owner will supply the exact 35-day input facts and independent spreadsheet outputs. This outline is not itself the golden fixture.
