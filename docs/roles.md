# Roles and permissions

Status: **P1 matrix approved by the product owner on 2026-10-12.** All permissions are tenant-scoped, denied by default, and enforced on every endpoint. Managers have assigned-farm scope. Workers never see money screens. Super Admin has no access to tenant business data by default, except the explicit reopen-flock action below.

Legend: **Y** = full; **V** = view only; **Own** = own entries only; **N** = none.

| Action/resource | Super Admin | Owner | Manager | Worker | Accountant |
|---|---|---|---|---|---|
| Manage tenants | Y | N | N | N | N |
| Users and roles (tenant) | N | Y | N | N | N |
| Farms and sheds | N | Y | Assigned farms (edit) | V | V |
| Flocks and placement | N | Y | Y | V | V |
| Daily records | N | Y | Y (7-day edit window) | Own, same day | V |
| Weight and feed use | N | Y | Y | Own, same day | V |
| Sales and payments | N | Y | Y | N | Y |
| Expenses | N | Y | Y | N | Y |
| Dashboard | N | Y (all farms) | Y (assigned farms) | V (limited) | Y (finance view) |
| Reports and export | N | Y | Y | N | Y |
| Close flock | N | Y | Y | N | N |
| Reopen flock | Y | Y | N | N | N |
| Audit log | N | Y | V | N | V |

## Policy notes

- Y grants the listed action within the user’s scope; V is read-only; Own limits writes to the user’s own entries. Any action not explicitly listed is denied.
- Manager permissions apply only to assigned farms. The Worker same-day and Manager seven-day daily-record windows follow D4; the matrix applies the same-day restriction to Worker weight and feed-use entries as specified by the owner.
- Workers must not see money screens. Accountant dashboard access is for finance views; operational data is view-only.
- Reopening is a narrow, audited action requiring a reason under D3; Super Admin permission does not grant tenant business-data access.
- P2 (invite-only onboarding), P3 (one tenant per user and farm assignment mechanics), and P4–P6 remain proposed in `decisions.md`; this approved matrix does not itself confirm those separate proposals.
