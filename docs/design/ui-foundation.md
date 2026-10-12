# Design tokens and role navigation

Status: Design proposal. All user-visible text is intended for locale resources; names below are content examples, not hard-coded UI strings.

## Design tokens

### Color

| Token | Value | Use |
|---|---|---|
| color-brand-700 | #0F5B55 | Primary actions, selected navigation |
| color-brand-900 | #103B39 | High-emphasis headings, dark brand surface |
| color-brand-50 | #E8F3F1 | Subtle selected/positive surface |
| color-accent-700 | #A85B00 | Warnings, attention; pair with icon and text |
| color-danger-700 | #B42318 | Errors/destructive actions; pair with label/icon |
| color-success-700 | #166534 | Saved/success state; pair with label/icon |
| color-text | #17211F | Primary text |
| color-text-muted | #52615E | Secondary text |
| color-border | #D5DEDB | Dividers and input borders |
| color-surface | #FFFFFF | Cards and controls |
| color-canvas | #F5F8F7 | Page background |
| color-focus | #155EEF | Visible keyboard focus ring |

Color contrast must be measured against WCAG AA before implementation. Status uses icon + words + color, never color alone. Respect system high-contrast and reduced-motion preferences.

### Type scale

Use a system sans-serif stack initially; do not download a font in the design phase. Use logical line-height and scalable rem units.

| Token | Size / line height | Typical use |
|---|---:|---|
| type-xs | 0.75rem / 1rem | timestamps, supporting labels |
| type-sm | 0.875rem / 1.25rem | field hints, dense metadata |
| type-md | 1rem / 1.5rem | body and input labels |
| type-lg | 1.125rem / 1.625rem | card titles |
| type-xl | 1.25rem / 1.75rem | section headings |
| type-2xl | 1.5rem / 2rem | page headings |
| type-3xl | 1.875rem / 2.25rem | dashboard headline values |

Do not use tiny text for form controls. Numeric values should include clear units.

### Spacing, shape, and touch

- Base spacing unit: 4 px. Tokens: space-1 4, space-2 8, space-3 12, space-4 16, space-5 20, space-6 24, space-8 32, space-10 40, space-12 48 px.
- Control height: minimum 44 px; daily-entry inputs/actions target 48–56 px.
- Corner radius: 6 px small controls, 10 px cards, 14 px sheets/dialogs.
- Border: 1 px; focus outline: 2 px with 2 px offset.
- Layout uses CSS logical properties (margin-inline, padding-inline, inset-inline-start) and supports RTL without mirrored one-off styles.
- On narrow screens, use one column; at wider breakpoints, expand grids without shrinking touch targets.

## Navigation by role

Navigation items are route-level modules and are hidden when the role lacks the corresponding endpoint permission. Server authorization remains authoritative.

| Role | Primary mobile navigation | Secondary/More | Notes |
|---|---|---|---|
| Worker | Home, My flocks, Daily entry | Profile/help | Never expose money screens, reports/export, users, or stock value. Daily entry is the prominent primary action. |
| Manager | Dashboard, Flocks, Daily, Sales | Feed, Expenses, Reports, Alerts, Audit | All farm data and edits are restricted to assigned farms; no user/role administration. |
| Owner | Dashboard, Farms, Flocks, Sales | Feed, Expenses, Reports, Users, Alerts, Audit, Settings | Dashboard spans all tenant farms; Owner can manage tenant users/roles. |
| Accountant | Finance, Sales, Expenses, Reports | Operations (view only), Profile | Finance dashboard and reports; operation routes are read-only. No flock close/reopen. |
| Super Admin | Tenants, System health | Profile | No tenant business navigation. Reopen is a narrow audited action reached only through an authorized support workflow, not tenant browsing. |

### Responsive behavior and interaction

- Phone: 4-item bottom navigation with 44 px minimum targets; overflow actions in a labeled More menu. Daily entry hides bottom navigation to preserve room and keeps Save sticky.
- Tablet/desktop: persistent side navigation with the same role-filtered groups; page content remains mobile-first.
- Use route-level code splitting, descriptive page titles, visible focus, and keyboard navigation.
- Keep all text, errors, status labels, navigation, units, and chart descriptions in i18n resources. Locale direction determines document direction; layout uses logical CSS.
