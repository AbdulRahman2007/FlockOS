POUKTRY DECISION LOG. Source of truth. Do not contradict it. Ask me before changing anything here.

CONFIRMED
D1  Multi-tenant SaaS: tenant_id on every business table, set server-side.
D2  Bird counts are derived: remaining = placed - mortality - culling - sold - transferred out (+ transferred in). No hand-edited totals.
D3  Edits: recompute the chain from the edited date, audit every edit, reject any edit that makes a closing count negative. Closed flocks are locked; only Owner or Super Admin can reopen, with a reason.
D4  Edit windows (configurable): Worker same day, Manager 7 days, Owner anytime.
D5  Mortality %: cumulative = deaths / placed. Daily or weekly = deaths / birds alive at period start. Culling tracked separately but included in total loss.
D6  FCR: cumulative headline plus daily trend. Running flock uses sampled average weight x birds alive. Final FCR uses total sold live weight. Dead-bird weight included. Placement weight subtracted. Raw FCR only in v1.
D7  Feed stock is per farm. Bags convert to kg via a configurable bag size. Stock = opening + purchases - usage - returns +/- adjustments.
D8  Profit: Estimated (uses the market price the user enters) and Actual (recorded sales) are separate labelled numbers, never mixed. Direct costs go to the flock; farm-level costs are allocated by birds x days (configurable).
D9  One daily record per flock per date (DB unique). A missed day is a flagged gap, never auto-filled with zeros. Idempotent submit. Daily form fields: deaths, culling, feed used, water, temperature, notes.
D10 Weight is a separate weekly sample entry (sample size and average weight).
D11 Online-only in v1. The form keeps drafts and retries on failure. Offline sync comes later.
D12 Sales: partial sales allowed. Fields: buyer, date, birds, total weight, rate per kg, amount, amount paid. Outstanding = sales - payments per buyer.
D13 Suppliers: a simple list linked to feed purchases and expenses. No payables ledger yet.
D14 In-app alerts: high mortality %, missing daily record, low feed cover, FCR worse than target. Thresholds configurable. Vaccination alerts deferred.

PROPOSED (not yet confirmed: ask me before treating as final)
P1  Roles. Super Admin: tenants and system health only. Owner: everything inside own tenant. Manager: operations, sales, expenses, close flocks and view audit log on assigned farms. Worker: same-day daily records, weights and feed use; no money screens. Accountant: sales, payments, expenses, finance dashboard and reports; view-only on operations.
P2  Invite-only accounts. Super Admin creates the owner; the owner invites everyone else. No public signup in v1.
P3  A user belongs to exactly one tenant. Managers and workers are assigned to specific farms.
P4  Super Admin has no access to tenant business data by default.
P5  Hosting: free tiers for dev and demo; a paid managed Postgres with daily backups for any real client data. Check current provider terms.
P6  Design target: 100 tenants and 1,000 users. Load-test beyond year-one volume.