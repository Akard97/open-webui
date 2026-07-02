# WorkOS — Sidebar-integrated access management (design)

Date: 2026-07-02 · Branch: `osool` · Status: approved by user (brainstorm 2026-07-02)

## 1. Goal

Retire the Access console *page* as a concept. All of its functionality moves into the
sidebar: workspace visibility (restrict / open up), restricted-workspace membership, and
team management (roster, roles, rename, archive, delete) become reachable from the rows
the user already navigates, via menus that open focused dialogs.

Design bar: professional, restrained, **not colorful** — neutral grays, shadcn primitives,
minimal accent color. (Note: this deliberately overrides the older "bold/colorful" taste
memory for this surface.)

User decisions (recorded):

| Question | Decision |
|---|---|
| Menu interaction | **Both** hover kebab (⋯) and right-click context menu, same items |
| Team management surface | **One "Team settings" dialog** with tabs (Members / General) |
| Workspace management surface | **One "Workspace settings" dialog** (visibility + members + danger zone) |
| Access console fate | **Remove frontend only** — backend `GET /access/overview` + its tests stay |
| Build approach | **A** — new dialog layer under `chrome/access/`, salvage roster logic from console components |

## 2. Constraints (from the access-control reference)

The reference doc `docs/superpowers/specs/2026-06-26-workos-access-control.md` remains the
source of truth. Rules this feature must mirror (UI mirrors only — the server stays
authoritative on every one):

- Frontend gating is **cosmetic**; every mutation goes through the existing gated endpoints
  (role gates, last-owner guard, restricted flip realtime protocol, socket eviction all
  server-side and unchanged).
- Team owner/admin manage members; **granting owner/admin is owner-only**
  (`team.members.grant_privileged`). Rename/archive/delete team is owner-only.
- Last-owner rows cannot be demoted/removed (`is_last_owner` mirror: `isLastOwner`).
- Workspace visibility flip `team→restricted` is destructive (evicts non-member sockets,
  disappears from sidebars) → requires an explicit confirm dialog. `restricted→team` needs
  no confirm.
- Restricted-workspace member picker offers **team members only** — the backend does not
  validate the target is a team member, the UI enforces the sane subset.
- App-admins (`user.role === 'admin'`) pass every owner gate server-side → treat as owners
  in the UI.
- No owner/admin bypass into restricted workspaces they aren't members of (§9 decision):
  a restricted workspace the manager can't see simply isn't in their bootstrap tree, so
  the sidebar never offers it. This surface therefore manages *visible* workspaces only —
  same posture as the console.

## 3. Entry points (Sidebar.svelte)

### Workspace rows
- Hover reveals a ⋯ kebab button (shadcn `DropdownMenu`); right-click opens a shadcn
  `ContextMenu` with the **same items**. Items defined once (plain array of
  `{label, icon, danger?, onSelect}`) and rendered by both menu flavors.
- Items (in order):
  1. **Workspace settings…** → opens the Workspace settings dialog
  2. **New workstream** → existing `{kind:'workstream'}` modal
  3. divider
  4. Quick visibility flip: **Restrict workspace…** (opens the same destructive confirm
     used by the dialog) or **Make team-visible…** (immediate, no confirm)
- Menu is offered only when the caller is team owner/admin or app-admin; other users get
  the plain row (no kebab, no context menu). The existing inline "New workstream" row
  under an expanded workspace stays.
- Restricted workspaces show a small lock icon on the row (`visibility` is already in the
  bootstrap payload — zero extra fetches).

### Team card
- The team switcher menu item "Manage members" becomes **Team settings…** (opens the Team
  settings dialog). Right-click on the team card opens a context menu with the same item.
- Gate: team owner/admin or app-admin (same as today's "Manage members" gate, i.e.
  `canManageMembers(role)` or app-admin).

## 4. Components (new: `src/lib/components/workos/chrome/access/`)

### `TeamSettingsDialog.svelte`
shadcn `Dialog` + `Tabs`.

- **Members tab** (owner/admin + app-admin):
  - Roster rows: initials avatar, name, role `Select` (owner/admin options disabled for
    non-owners), overflow kebab → "Remove from team".
  - Last-owner row: role select + remove replaced by a locked "Last owner" hint.
  - Add row: user `Select` (candidates = `listAllUsers(teamId)` minus current members via
    `addableUsers`), role `Select` (owner may grant any role; admin only `member`), Add
    button.
- **General tab** (owner + app-admin only — tab hidden for non-owner admins):
  - Rename (input + save on Enter/blur).
  - Archive / Unarchive toggle button.
  - Danger zone: **Delete team** → nested destructive confirm dialog (permanent, cascades
    to workspaces/workstreams/tasks).

### `WorkspaceSettingsDialog.svelte`
shadcn `Dialog`, single column.

- **Visibility**: two radio-card options — *Team-visible* ("Everyone on the team can see
  it.") and *Restricted* ("Only explicit members and the creator."). Selecting
  *Restricted* from *team* opens the destructive confirm (wording preserved from the
  console: members-only visibility, immediate loss of access, live sessions disconnected,
  members can be added back afterwards). Selecting *Team-visible* applies immediately.
- **Members** (rendered only while `restricted`): rows with avatar, name, role `Select`
  (admin/member), remove ×; add row with team-member picker (`addableWorkspaceMembers`) +
  role select. Empty state: "No explicit members — only the creator and admins can see
  this."
- **Rename**: input + save (net-new UI; `PATCH /workspaces/{id}` already accepts `name`).
- **Danger zone**: **Delete workspace** → nested destructive confirm
  (`DELETE /workspaces/{id}`, team owner/admin gate server-side). Net-new UI; endpoint
  exists and is gated.

### Menus
No separate component needed if item lists stay small: the Sidebar defines the action
array and renders `DropdownMenu.Content` and `ContextMenu.Content` from it. If that
duplication grows, extract a snippet — implementation detail, not a contract.

## 5. Wiring & data flow

- `store.ts` `ModalRequest` union: **remove** `{kind:'members'}`, **add**
  `{kind:'team-settings'; teamId: string}` and
  `{kind:'workspace-settings'; workspaceId: string}`.
- Both dialogs are mounted alongside `ModalHost` in `WorkOSApp.svelte` and driven by
  `openModal` (single host pattern preserved). `ModalHost` keeps the three create flows
  and loses its `members` branch.
- On open: Team dialog fetches `listTeamMembers` + `listAllUsers`; Workspace dialog
  fetches `listWorkspaceMembers` (when restricted) — same lazy-load posture as the
  console.
- After any mutation: refetch the dialog's own data (refetch-on-finally so a rejected
  change snaps back). Additionally:
  - roster changes → `reloadDirectory()`
  - tree-affecting ops (team rename/archive/delete, workspace rename/delete, visibility
    flip) → `loadBootstrap()`. Visibility-flip realtime events
    (`workspace.deleted`-shaped + rebuild) are already handled by the store; the
    bootstrap reload is belt-and-braces for the actor's own client.
- Permission mirrors come from existing `roles.ts` predicates + the `roles` store;
  app-admin from the OWUI `user` store. Both menus (workspace rows and team card) gate on
  `canManageMembers(teamRole) || app-admin` — the sidebar has no workspace-member role to
  consult. `canManageWorkspace` stays as-is (it is *not* dead: `canEditTask` /
  `canEditSubtask` call it; the reference doc's "unused" note is stale and gets corrected
  in the same change).

## 6. Removal scope (frontend only)

Deleted:
- `views/access/` — all six components (`AccessConsole`, `TeamList`, `TeamDetail`,
  `MemberRoster`, `WorkspacePanel`, `WorkspaceMembersPanel`); roster/members logic is
  salvaged into the two new dialogs first.
- `'access'` view key + its guard in `WorkOSApp.svelte`; both shield buttons in
  `Sidebar.svelte`.
- `canUseAccessConsole` predicate + its tests in `roles.ts` / `roles.test.ts`.
- `filterOverview` helper + its tests (console-only).
- `api.accessOverview` + the `AccessTeamOverview` / `AccessWorkspaceSummary` types.
- `ModalHost`'s `members` branch (superseded by the Team settings dialog).

Kept:
- **Backend `GET /access/overview` endpoint + `test_router_access_overview.py`** (user
  decision: frontend-only removal; the aggregate endpoint may serve a future view).
- `accessConsole.ts` survivors (`addableUsers`, `addableWorkspaceMembers`, `isLastOwner`)
  → file renamed to `lib/members.ts` (tests move to `members.test.ts`); imports updated.

## 7. Dependencies

- shadcn-svelte: add **`context-menu`** (only missing primitive; dialog, tabs, select,
  dropdown-menu, avatar, separator, input, button already installed). Destructive confirms
  reuse `Dialog` (existing pattern) — no `alert-dialog` addition.

## 8. Error handling

- Every mutation: `try / toast.error(detail) / finally refetch` — identical posture to the
  console (`svelte-sonner`), so server rejections (403 role, last-owner 400, invalid role)
  surface as toasts and the UI snaps back to server truth.
- Dialog fetch failures degrade to empty lists with the existing `.catch(() => [])`
  pattern; no crash, controls disabled by emptiness.

## 9. Testing

- Vitest: helper tests move with the `members.ts` rename (coverage unchanged);
  `roles.test.ts` drops `canUseAccessConsole` cases; if `canManageWorkspace` is reused its
  existing tests stand, if removed they go with it.
- No component-test infra exists for WorkOS Svelte components — dialogs are covered by
  manual browser smoke (user's own Vite hot-reload server; do not start one unasked).
- Backend untouched → backend test suite untouched (access-overview tests stay green).
- The access-control reference doc §6 must be updated in the same change (console
  references → sidebar dialogs), per the standing sync rule.

## 10. Out of scope

- Any backend change (endpoints, gates, realtime).
- Restyling the three create modals in `ModalHost` (separate polish task).
- Workspace-admin (non-team-admin) menu access: a workspace member with role `admin` who
  is not a team owner/admin does not get the sidebar menu — same limitation the console
  had (its gate was identical). Server-side they could still manage via API; revisit only
  if a real user hits it.
