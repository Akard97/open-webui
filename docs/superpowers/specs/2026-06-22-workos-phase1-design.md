# WorkOS — Phase 1 Design (Core Spine + Realtime + Admin Center)

**Date:** 2026-06-22
**Status:** Approved (design); pending spec review
**Tool route:** `/workos` (placeholder exists today)
**Pattern reference:** Policy Review (`models/policy_review.py`, `routers/policy_review.py`, `src/lib/components/policy-review/`)

---

## 1. Overview

WorkOS is a task-management tool inside Osool (this Open WebUI fork). It replaces the
current `/workos` placeholder with a real, persisted, membership-scoped task manager.

The UX is taken from the user's prototype (`Osool Task App.html`): a hierarchy of
**Team → Workspace → Workstream → Task**, with Board (kanban) and List views, a task-detail
slide-over, and per-task fields (status, priority, assignee, due date, labels, progress).

This document covers **Phase 1** only. Phases 2 and 3 are sketched in §12.

### Hierarchy

```
Team (e.g. "Acme", key OSL)
  └── Workspace (e.g. "Engineering")   visibility: team | restricted
        └── Workstream (e.g. "Platform")
              └── Task (OSL-2841)
```

---

## 2. Goals & non-goals

### Phase 1 goals
- Persisted Team / Workspace / Workstream / Task model owned by WorkOS.
- Members and assignees are **real Open WebUI users** (FK to `user.id`).
- **Membership-scoped access** with roles (owner / admin / member) at Team and Workspace level.
- Board (kanban, drag-and-drop) and List views; full task CRUD with core fields.
- Task-detail slide-over (editable properties + description).
- **Realtime**: add/move/edit propagates to everyone viewing the same workstream without refresh, reusing the existing Socket.IO infrastructure.
- A lean **WorkOS Admin Center** (in-tool, tabbed) for access docs, cross-team oversight, and global rules.
- Notifications are **designed-for** (event payloads + emit paths are notification-ready) but **not built** in Phase 1.

### Non-goals (Phase 1)
Comments, attachments, @mentions, notifications (stored/delivered), the *My Work*
dashboard, Timeline/Gantt view, saved views, per-workspace custom statuses/priorities,
cross-team task references.

---

## 3. Decisions (locked)

| Topic | Decision |
|---|---|
| Identity | Hybrid: real OWUI users as members/assignees; WorkOS owns Team/Workspace/Workstream/Task/Label tables |
| Access | Membership-scoped + roles (owner / admin / member) |
| Membership level | Team + Workspace; Workstreams inherit Workspace access |
| Visual approach | Hybrid: tool-local `styles.css` for WorkOS layout, reuse shared primitives (buttons, inputs, avatars, icons) where they exist |
| Board interaction | Drag-and-drop (via `sortablejs`, already a dependency) + status-menu fallback |
| Realtime | Phase 1, reuse Socket.IO (`socket/main.py`, client `socket` store) |
| Notifications | Phase 2; payloads/paths reserved now |
| Admin center | Phase 1, lean tabbed in-tool view (Access / Teams / Rules) |
| Statuses/priorities | Fixed enums in Phase 1; customization deferred |
| Labels | Per-team label set; attached to tasks as an id array |
| Task keys | Per-team prefix + auto-increment (`OSL-2841`) via `workos_team.task_seq` |

---

## 4. Architecture & file layout

Mirrors the Policy Review tool.

### Backend
- `backend/open_webui/models/workos.py` — SQLAlchemy tables + Pydantic schemas + async DAO classes (using `Base`, `get_async_db_context`).
- `backend/open_webui/routers/workos.py` — APIRouter mounted at `/api/v1/workos`; every endpoint enforces membership/role.
- `backend/open_webui/socket/main.py` — add a `@sio.on('workos:subscribe')` handler + emit helpers (see §8).
- Alembic migration creating the Phase 1 tables.
- `backend/open_webui/internal/workos/seeder.py` — optional, env-gated dev seeder that plants the prototype's *Acme → Engineering → Platform* demo data for the current admin (mirrors the Policy Review seeder).
- `backend/open_webui/config.py` — add `features.workos` and `features.workos_admin` permission flags + `PersistentConfig` entries for global WorkOS rules (§9).
- `backend/open_webui/test/workos/` — pytest router tests.

### Frontend (`src/lib/components/workos/`)
- `WorkOSApp.svelte` — root; replaces the placeholder; store-driven view switching (board / list / task / admin); active workstream reflected in the URL for deep links.
- `chrome/Sidebar.svelte` — team switcher, Workspaces/Workstreams nav + create buttons, footer (reuse existing `ThemeSwitcher`), admin entry (gated).
- `chrome/Topbar.svelte` — breadcrumb, Board/List tabs (Timeline hidden in v1), search (client-side filter), New-task, basic filters.
- `views/BoardView.svelte` — kanban columns by status, drag-and-drop + status menu, inline add.
- `views/ListView.svelte` — dense grouped rows, status icon, multi-select.
- `views/TaskDetail.svelte` — slide-over; editable properties + description; comments/activity tab stubbed "Phase 2".
- `views/modals/` — create/edit Team, Workspace, Workstream; manage members (user search + role).
- `views/admin/AdminApp.svelte` + `AccessTab.svelte` / `TeamsTab.svelte` / `RulesTab.svelte`.
- `lib/api.ts` — typed fetch wrappers.
- `lib/store.ts` — state, socket subscription, optimistic patching, event reconciliation.
- `lib/types.ts` — shared types.
- `lib/roles.ts` — authorization helpers (pure, unit-tested).
- `lib/key.ts` — task-key/number helpers (pure, unit-tested).
- `styles.css` — tool-local tokens.
- `src/routes/(app)/workos/` — `+layout.svelte` (already suppresses chat sidebar) + `+page.svelte` (mounts `WorkOSApp`).

---

## 5. Data model (Phase 1 tables)

All ids are `Text` UUIDs. `created_at` / `updated_at` / `completed_at` are nanosecond
epochs via `int(time.time_ns())` (matching the Policy Review convention). `due_date` is a
millisecond epoch (date granularity, nullable). User references are `Text` FKs to `user.id`
(not enforced as DB FKs, matching OWUI's loose-coupling convention).

### `workos_team`
| col | type | notes |
|---|---|---|
| id | Text PK | uuid |
| key | Text unique | short prefix, e.g. `OSL` |
| name | Text | |
| icon | Text nullable | icon name/color token |
| task_seq | BigInteger | counter for per-team task numbers, starts 0 |
| archived | Boolean | default false |
| created_by_id | Text | |
| created_at / updated_at | BigInteger | |

### `workos_team_member`
| col | type | notes |
|---|---|---|
| id | Text PK | |
| team_id | Text | |
| user_id | Text | → `user.id` |
| role | Text | `owner` / `admin` / `member` |
| created_at | BigInteger | |
| | UniqueConstraint(team_id, user_id) | |

### `workos_workspace`
| col | type | notes |
|---|---|---|
| id | Text PK | |
| team_id | Text | |
| name | Text | |
| icon | Text nullable | |
| visibility | Text | `team` (all team members) / `restricted` (workspace members only) |
| archived | Boolean | default false |
| created_by_id | Text | |
| created_at / updated_at | BigInteger | |

### `workos_workspace_member`
| col | type | notes |
|---|---|---|
| id | Text PK | |
| workspace_id | Text | |
| user_id | Text | → `user.id` |
| role | Text | `admin` / `member` |
| created_at | BigInteger | |
| | UniqueConstraint(workspace_id, user_id) | only enforced when `visibility=restricted` |

### `workos_workstream`
| col | type | notes |
|---|---|---|
| id | Text PK | |
| workspace_id | Text | |
| name | Text | |
| icon | Text nullable | |
| archived | Boolean | default false |
| created_by_id | Text | |
| created_at / updated_at | BigInteger | |

### `workos_label`
| col | type | notes |
|---|---|---|
| id | Text PK | |
| team_id | Text | per-team |
| name | Text | |
| color | Text | token |
| created_at | BigInteger | |

### `workos_task`
| col | type | notes |
|---|---|---|
| id | Text PK | |
| workstream_id | Text | |
| team_id | Text | denormalized (for keying + cross-workstream queries) |
| number | BigInteger | per-team sequential |
| key | Text | display key `OSL-2841` (prefix + number) |
| title | Text | |
| description | Text nullable | |
| status | Text | `backlog` / `todo` / `in_progress` / `in_review` / `done` / `canceled` |
| priority | Text | `urgent` / `high` / `medium` / `low` (nullable → "no priority") |
| assignee_id | Text nullable | → `user.id` |
| due_date | BigInteger nullable | |
| progress | Integer | 0–100, default 0 |
| labels | JSON | array of `workos_label.id` |
| sort_key | Float | ordering within a status column (for DnD) |
| created_by_id | Text | |
| completed_at | BigInteger nullable | set when status → `done` |
| created_at / updated_at | BigInteger | |

### Reserved for Phase 2 (NOT created in Phase 1)
- `workos_notification` — per-user notification inbox.
- `workos_activity` — activity/audit log feeding the activity tab + dashboard.
- `workos_comment`, `workos_attachment`.

### Task key & ordering
- On task create: atomically increment `workos_team.task_seq`, set `number`, compute `key = f"{team.key}-{number}"`.
- `sort_key` is a float; new tasks get `max(sort_key in column) + STEP`. DnD sets `sort_key` to the midpoint between neighbors (rebalance pass if floats converge — covered by unit tests).

---

## 6. Authorization

Pure helpers in `lib/roles.ts` (frontend) and mirrored server-side in `routers/workos.py`.
Server is the source of truth; the client copy only drives UI affordances.

### Visibility
- **Team**: visible iff requester is a team member (any role) — or a system admin.
- **Workspace**: visible iff team-visible AND (`visibility=team` OR requester is a workspace member).
- **Workstream / Task**: visible iff its Workspace is visible.

### Mutation matrix
| Action | Allowed roles |
|---|---|
| Create team | any user with `features.workos` (subject to the "who may create teams" rule, §9) |
| Rename/archive/delete team, manage owners/admins | team `owner` |
| Manage team members (non-owner), create/edit/archive workspaces | team `owner` / `admin` |
| Edit workspace, manage workspace members, create workstreams | team owner/admin OR workspace `admin` |
| Rename/archive workstream | team owner/admin OR workspace admin |
| Create/edit task (status, priority, assignee, due, labels, progress, sort, title, desc) | any member who can see the workstream |
| Delete task | task creator OR team/workspace admin |
| Manage labels | team owner/admin |
| Admin Center | system admin OR `features.workos_admin` |

System admins implicitly pass all checks (matching Policy Review's "admins always have all").

---

## 7. API surface (`/api/v1/workos`)

Every route resolves the requesting user, then enforces §6. Responses are Pydantic models.

- `GET /bootstrap` → `{ teams, workspaces, workstreams, my_roles }` — the nav tree the current user can see, in one call.
- **Teams**: `GET /teams`, `POST /teams`, `GET /teams/{id}`, `PATCH /teams/{id}`, `DELETE /teams/{id}`.
  - Members: `GET /teams/{id}/members`, `POST /teams/{id}/members`, `PATCH /teams/{id}/members/{user_id}`, `DELETE /teams/{id}/members/{user_id}`.
- **Workspaces**: `GET /teams/{id}/workspaces`, `POST /teams/{id}/workspaces`, `GET /workspaces/{id}`, `PATCH /workspaces/{id}`, `DELETE /workspaces/{id}`.
  - Members: `GET /workspaces/{id}/members`, `POST`, `PATCH`, `DELETE` (same shape as team members).
- **Workstreams**: `GET /workspaces/{id}/workstreams`, `POST /workspaces/{id}/workstreams`, `PATCH /workstreams/{id}`, `DELETE /workstreams/{id}`.
- **Tasks**: `GET /workstreams/{id}/tasks`, `POST /workstreams/{id}/tasks`, `GET /tasks/{id}`, `PATCH /tasks/{id}`, `DELETE /tasks/{id}`.
- **Labels**: `GET /teams/{id}/labels`, `POST /teams/{id}/labels`, `PATCH /labels/{id}`, `DELETE /labels/{id}`.
- **Admin**: `GET /admin/teams` (cross-team oversight), `GET /admin/settings`, `PATCH /admin/settings`.
- **User picker**: reuse the existing `GET /api/v1/users/` listing endpoint (`users.py` `get_users`) for assignee/member search — no new endpoint.

---

## 8. Realtime (Socket.IO reuse)

### Server
- New handler `@sio.on('workos:subscribe')` in `socket/main.py`: payload `{ team_id?, workspace_id?, workstream_id? }`. The handler **re-validates visibility** for the requesting user (same checks as §6), then `sio.enter_room(sid, room)` for:
  - `workos:workstream:{id}` — task-level events
  - `workos:team:{id}` — nav-level events (new workspace/workstream, renames)
- New handler `@sio.on('workos:unsubscribe')` → `sio.leave_room`.
- After each mutating route commits, the router emits to the relevant room(s) via `sio.emit(event, payload, room=...)`. Events:
  - `workos:task.created` / `task.updated` / `task.moved` / `task.deleted` → `workos:workstream:{id}`
  - `workos:workstream.created/updated/deleted`, `workos:workspace.created/updated/deleted` → `workos:team:{id}`
- Payloads carry the full changed entity (or id for deletes) and an `actor_id`, so they are notification-ready for Phase 2.

### Client
- `lib/store.ts` uses the global `socket` (`src/lib/stores/index.ts`). On view change it emits `workos:subscribe` for the active workstream/team and listens for the events above, **patching store state** so other users' changes appear live.
- Local mutations are optimistic; the server broadcast reconciles (the actor ignores its own echo by `actor_id`/local op id).
- On unmount / view change it unsubscribes from the previous rooms.

---

## 9. Admin Center (Phase 1, lean)

In-tool tabbed view (`views/admin/AdminApp.svelte`), reached from the WorkOS sidebar,
gated by **system admin OR `features.workos_admin`**.

- **Access tab** — documents `features.workos` (use the tool) and `features.workos_admin` (this center); links to `/admin/users/groups`. Mirrors Policy Review's `AccessTab.svelte`.
- **Teams tab** — cross-team oversight: every team with owner + member counts; transfer ownership, archive, delete. Backed by `GET /admin/teams`.
- **Rules tab** — global settings via `PersistentConfig`, backed by `GET/PATCH /admin/settings`:
  - who may create teams (`all_users` | `admins_only`)
  - default workspace visibility (`team` | `restricted`)
  - the fixed status/priority sets (read-only display in v1)
  - task-key rules (display)
  - **Notifications** sub-section is added here in Phase 2.

### Config additions (`config.py`)
- Permission flags: `features.workos`, `features.workos_admin` (group-grantable; admins always have them).
- `PersistentConfig` entries for the Rules tab (team-creation policy, default visibility).
- The rail item (`railItems.ts`) stays visible to everyone; an empty-state ("you're not in any teams yet") shows for users with no memberships.

---

## 10. Testing

- **vitest** (`lib/*.test.ts`): `roles.ts` (full mutation/visibility matrix), `key.ts` (number→key, sort-rank midpoint + rebalance), `store.ts` (optimistic apply + socket-event reconciliation, dedupe own echo).
- **pytest** (`backend/.../test/workos/`): membership/role enforcement per endpoint, task-key sequencing under concurrent create, DnD `sort_key` persistence, that mutations emit the right Socket.IO events to the right rooms (emit mocked), and that `workos:subscribe` rejects rooms the user can't see.

---

## 11. Migration & seeding

- One Alembic migration creates the Phase 1 tables (§5). Reserved Phase 2 tables are **not** included.
- `internal/workos/seeder.py` (env-gated, e.g. `WORKOS_SEED_DEMO`, default off) seeds the prototype's demo data (Acme team, Engineering/Design workspaces, Platform/Mobile/Growth/Brand workstreams, the 10 sample tasks, the 6 labels) owned by the first/current admin. For dev/demo only.

---

## 12. Future phases (sketch, not in scope)

- **Phase 2 — Collaboration & notifications:** `workos_comment`, `workos_attachment` (reuse OWUI file storage), `workos_activity`, `workos_notification`; @mentions; Inbox; assignee/mention delivery via `emit_to_users(..., user:{id})`; Notifications sub-tab in the Admin Center.
- **Phase 3 — Dashboards & polish:** *My Work* home (stat cards + assigned-to-you + activity feed), Timeline/Gantt view, filters/search/display options, saved views.

---

## 13. Risks & open items

- **`sort_key` float convergence** under heavy reordering → mitigated by a rebalance pass (unit-tested). Alternative (lexorank) deferred unless needed.
- **Realtime authorization drift**: room membership is validated at subscribe time; a user removed from a team mid-session keeps their socket room until reconnect/next subscribe. Acceptable for Phase 1 (data still re-checked on every HTTP read); revisit if it matters.
- **`sortablejs` + Svelte 5 runes** integration: confirm the action pattern during implementation (the lib is already a dependency, used elsewhere in the app).
- **Workspace `restricted` UX**: Phase 1 ships the visibility flag + workspace membership; the management UI for restricted workspaces is minimal (add/remove members). Polish later.
