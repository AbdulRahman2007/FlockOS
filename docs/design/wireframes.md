# Low-fidelity mobile wireframes

Status: Design proposal for review. These are interaction layouts, not visual assets or UI code. Mobile reference viewport: 360 × 800 CSS px; target touch area is at least 44 × 44 px.

## Daily entry — single screen

The worker opens the assigned flock from the limited dashboard or a saved shortcut. Farm, shed, flock, and today's Asia/Karachi date are preselected. The form fits on one screen at the reference viewport; no wizard/next steps. All labels and validation messages come from i18n resources.

```text
┌──────────────────────────────────────┐
│ ← My flocks             [Profile]    │  56 px
├──────────────────────────────────────┤
│ Shed 2 · Flock B-17        TODAY ▾   │
│ Mon, 12 Oct 2026 · 4,855 birds       │  Context is server-derived
├──────────────────────────────────────┤
│ DAILY RECORD                         │
│                                      │
│ Deaths             Culling           │
│ ┌────────────────┐ ┌────────────────┐│
│ │ 0          #   │ │ 0          #   ││  inputMode numeric
│ └────────────────┘ └────────────────┘│  48 px inputs
│                                      │
│ Feed used               [kg / bag ▾] │
│ ┌──────────────────────────────────┐ │
│ │ 0.0                          #   │ │
│ └──────────────────────────────────┘ │
│                                      │
│ Water (liters)        Temperature (°C) │
│ ┌────────────────┐ ┌────────────────┐│
│ │ Add amount     │ │ Add reading    ││  Optional until
│ └────────────────┘ └────────────────┘│  requiredness is agreed
│                                      │
│ Notes (optional)                     │
│ ┌──────────────────────────────────┐ │
│ │                                  │ │
│ └──────────────────────────────────┘ │
│                                      │
│ [Saved locally as draft · Retry ready]│  shown when relevant
├──────────────────────────────────────┤
│ [ Save today's record             ]  │  56 px sticky action
└──────────────────────────────────────┘
```

### Interaction and error states

- Deaths, culling, and feed fields use the numeric keypad. Zero is an explicit value only when the worker submits; the system never creates a record just because defaults are shown.
- Feed accepts kg or bags and converts bags using the farm's configured bag size; the conversion used is retained with the fact. Water is entered in liters and temperature in °C.
- Save sends one idempotency key. On a timeout, preserve all typed values, show “Not saved yet — retry”, and retry with the same key. On confirmed success, show saved status and prevent accidental duplicate submission.
- Validation appears beside the field in plain language and explains the correction. If deaths/culling would make a derived closing count negative, reject save and retain the draft.
- Show a loading state on the save action. A missed date is a separate flagged gap; this form never silently fills past dates with zero.
- Weight sampling is not mixed into daily entry: it is a separate weekly action on flock detail per D10.
- Dead-bird weights are entered as separate mortality weight entries attached to the saved daily record, keeping the one-screen daily form compact. The entries capture bird count and combined weight; FCR treats a day's dead biomass as complete only when the entered count covers that day's recorded deaths.
- If the viewport is too short or text is enlarged, allow vertical scroll without losing the sticky save target or form state.

## Operational dashboard

```text
┌──────────────────────────────────────┐
│ POUKTRY             Farm ▾  Profile  │
├──────────────────────────────────────┤
│ Good morning                         │
│ [Farm selector / assigned farm]      │
│                                      │
│ TODAY                                │
│ ┌──────────────┐ ┌─────────────────┐ │
│ │ Records      │ │ Missing records │ │
│ │ 8 / 9        │ │ 1 · Shed 2     │ │
│ └──────────────┘ └─────────────────┘ │
│                                      │
│ ALERTS                               │
│ ! Flock B-17 mortality above target  │
│ ! Feed cover low · Shed 1            │
│                                      │
│ ACTIVE FLOCKS                        │
│ B-17 · Shed 2          4,855 birds   │
│ Mortality 0.8% · FCR 2.44            │
│ [Open flock]                         │
│                                      │
│ [ + Enter daily record ]             │  Worker / Manager
├──────────────────────────────────────┤
│ Home     Flocks     Daily     More   │
└──────────────────────────────────────┘
```

- Owner sees all farms; Manager sees assigned farms; Worker sees limited operational cards and no monetary values; Accountant has a separate finance dashboard and read-only operations view.
- Render charts with labels, units, and direct data values so color is not the only signal. Loading skeletons reserve chart/card space; empty/error states explain what to do.
- Dashboard totals carry a “Data through” timestamp when a projection is stale or delayed.

## Flock detail

```text
┌──────────────────────────────────────┐
│ ← Flocks                 [More ▾]    │
├──────────────────────────────────────┤
│ B-17 · Shed 2                        │
│ Active · placed 7 Sep                │
│                                      │
│ 4,855 birds remaining                │  calculated, not editable
│ Mortality 0.8%     Raw FCR 2.44      │  server values
│                                      │
│ [ Daily ] [ Weights ] [ Feed ]       │  horizontal tabs
│ [ Sales ] [ Costs ] [ Activity ]     │  hidden when role lacks access
│                                      │
│ TODAY                                │
│ No record submitted yet              │
│ [ Enter today's record ]             │
│                                      │
│ RECENT ACTIVITY                      │
│ 12 Oct · 30 deaths · 5 culled        │
│ 11 Oct · Daily record submitted      │
│                                      │
│ [ Close flock ]                      │  Owner / Manager only;
│                                      │  reason workflow on reopen
├──────────────────────────────────────┤
│ Home     Flocks     Daily     More   │
└──────────────────────────────────────┘
```

Worker and Accountant views omit actions and monetary tabs they cannot use. Accountant operational data is view-only. Confirm close/reopen actions; reopen requires Owner/Super Admin and a reason. Flock detail never offers direct editing of derived bird totals.
