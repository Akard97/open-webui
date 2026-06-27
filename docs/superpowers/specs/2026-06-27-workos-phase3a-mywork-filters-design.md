<!--
  WorkOS Phase 3a — My Work + Filters/Search: design spec.
  Branch: osool. Created 2026-06-27.
  Brainstormed interactively; decisions captured in §2. This is the first slice of the
  decomposed Phase 3 (see §1). Access-control-sensitive — keep
  docs/superpowers/specs/2026-06-26-workos-access-control.md in sync (standing rule).
-->

# WorkOS Phase 3a — My Work + Filters/Search (Design)

## 1. Context & decomposition

WorkOS Phases 1–2 ([workos-phase1], [workos-phase2]) built the Team → Workspace → Workstream → Task tree, collaboration (comments/attachments/activity/@mentions), notifications + inbox, and the access-control hardening (gaps G1–G11 closed). Everything to date is **per-workstream and in-memory**: the frontend loads tasks only for the currently selected workstream, and the backend exposes a single task query, `list_for_workstream(id)`, with no query params.

"Phase 3" as originally framed bundles five fairly independent features: a My Work dashboard, Timeline/Gantt, saved views, filters/search, and a Phase-1 realtime carry-over. That is too large for one spec, so it is **decomposed**. This document specifies **Phase 3a — the foundation slice**:

- **My Work** — the first cross-workstream surface.
- **Filters + scoped search** — a shared bar wired into the existing board/list **and** My Work.
- **Realtime carry-over** — live sidebar nav + live My Work.

Deferred to their own later slices (each gets its own spec → plan → build): **Timeline/Gantt**, **Saved Views** (persisted filter presets), **global jump-to search**, and **URL routing / task deep-linking**. The filter model in §5 is designed so Saved Views can serialize it later without rework.

## 2. Locked decisions

Captured during brainstorming (2026-06-27):

| # | Decision | Choice |
|---|---|---|
| D1 | What My Work aggregates | Tasks **assigned to OR created by** the current user, across **all** their teams/workspaces they can see. |
| D2 | Default grouping | **Due-date urgency buckets**: Overdue / Today / This week / Later / No date. |
| D3 | Filter+search placement | **Shared bar** on board/list (filters the current workstream) **and** My Work (filters the fetched union). |
| D4 | Search semantics | **Scoped** — narrows the current list only; case-insensitive match on task **title + key**. No new search endpoint. |
| D5 | Assigned-vs-created presentation | **Segmented toggle**: All / Assigned / Created, sitting above the buckets. |
| D6 | My Work realtime | **Live across all my workstreams** while My Work is open. |
| D7 | §5 restricted-workspace nav leak | **(A) client-side guard** this slice; server-side room re-scoping deferred as the tracked §5 follow-up. |
| D8 | My Work placement / default | Top sidebar entry **above** the team switcher; **default landing view** when WorkOS opens. |

## 3. Goals / non-goals

**Goals**
- A user can open WorkOS and immediately see everything on their plate across every team, organized by urgency, and narrow it with the same filter controls used on the board.
- Filters and scoped search work identically on the board, the list, and My Work via one shared, pure, tested engine.
- The sidebar and My Work update live, without manual refresh.

**Non-goals**
- Timeline/Gantt, persisted Saved Views, global search, URL deep-linking (deferred slices).
- New persisted data / DB migration. This slice adds only a read-only aggregate endpoint and frontend behavior.
- Changing the access-control model. The new endpoint **consumes** the existing model; it must not widen visibility.

## 4. Backend — `GET /api/v1/workos/me/tasks`

A single new read-only endpoint returning a flat, de-duplicated `Task[]` — the union of tasks assigned to the caller and tasks created by the caller, restricted to what the caller may currently see.

### 4.1 Gate & visibility (access-control-sensitive)

- Authenticated via `get_verified_user` + `_require_workos` (same as every WorkOS route). Intrinsically scoped to `user.id`; no team/workstream path param.
- **Every candidate task is filtered through `can_see_workstream(user.id, is_admin, task.workstream_id)` before it is returned.** A task the caller created in a workspace they have since lost visibility to — or was assigned to but cannot see — is **excluded**. This keeps the aggregate consistent with `require_task_visible` and with the G1/G3/G4 notification-leak fixes: assignment/authorship is **not** an access grant.
- App-admins (`role=='admin'`) see their own assigned/created tasks the same way; the admin super-user bypass in `can_see_workstream` means they are never *excluded* by visibility, which is consistent with existing behavior.

### 4.2 Query strategy

`WorkosTask` carries a denormalized `team_id`. New DAO method on `Tasks` (models/workos.py):

```
list_for_user(user_id, team_ids, db=None) -> list[TaskModel]
```

1. `team_ids` = teams the user belongs to (admin → all teams).
2. Fetch candidates by `team_id IN team_ids`.
3. In Python, keep a task iff (`user_id in task.assignee_ids` **or** `task.created_by_id == user_id`).
4. The router then drops any task failing `can_see_workstream` (§4.1) and de-dupes (a task where the caller is both creator and assignee appears once).

**Why Python-side membership filtering:** `assignee_ids` is a JSON column; "list contains value" has no portable SQL form across SQLite and Postgres (both are supported runtimes). Filtering candidates by the indexed-ish `team_id` first bounds the in-memory set to the caller's teams. For very large teams this is more rows than ideal; a denormalized assignee-index table (or DB-specific JSON operators) is a **documented future optimization**, out of scope here.

### 4.3 Response shape

A flat `TaskModel[]` (same shape `list_for_workstream` returns, including computed `subtask_total`/`subtask_completed`). **No server-side All/Assigned/Created split** — the client derives the segment (D5) from `created_by_id`, `assignee_ids`, and the current user id it already holds. Likewise grouping (D2) and filtering (D3) are client-side.

### 4.4 Access-control doc update (standing rule)

In the **same change**, add this endpoint to §4 of `docs/superpowers/specs/2026-06-26-workos-access-control.md` (Tasks table or a new "Aggregate" row), documenting: `_require_workos`; intrinsically user-scoped; **per-task `can_see_workstream` filter**; returns assigned ∪ created. No new gap is introduced; note explicitly that assignment/authorship still confer no access — the filter enforces it.

## 5. Filters & scoped search — one shared, pure engine

Two new pure, framework-free modules under `src/lib/components/workos/lib/` (unit-tested in isolation):

- **`filters.ts`** — a `TaskFilter` type and pure `matchesFilter(task, filter, ctx)` / `applyFilters(tasks, filter, ctx)`.
  - Facets: `statuses`, `priorities`, `labelIds`, `assigneeIds` (sets; empty set = "any"), and `text`.
  - `text` is case-insensitive, matched against `title` **and** `key` (D4). Empty string = no text constraint.
  - An empty `TaskFilter` is the identity (returns all tasks) — so mounting the bar never hides anything until the user picks something.
- **`buckets.ts`** — `bucketByDueDate(tasks, now) -> { overdue, today, thisWeek, later, noDate }` (D2). `now` is injected for testability. Boundaries are explicit, local-time, and rolling (not calendar-week, to avoid edge ambiguity):
  - `overdue` — `due_date < start-of-today` (past due).
  - `today` — `start-of-today ≤ due_date ≤ end-of-today`.
  - `thisWeek` — `end-of-today < due_date ≤ end-of-today + 7 days`.
  - `later` — `due_date > end-of-today + 7 days`.
  - `noDate` — `due_date == null`.

**Shared component `chrome/FilterBar.svelte`:**
- Renders facet dropdowns (Status, Priority, Label, Assignee) + a search input, bound to a `TaskFilter`.
- Replaces BoardView's current **disabled "Coming soon"** placeholder buttons; the same component mounts on List and My Work.
- **On My Work**, the **Assignee** facet is replaced by the **All / Assigned / Created** segment (D5) — filtering your own list by assignee is redundant; the segment occupies that slot.

**Execution is entirely client-side (D3/D4):** the board/list already hold their workstream's tasks in the `tasks` store; My Work holds the fetched union in `myTasks`. One engine, two data sources. No backend filtering, no new query params on `list_for_workstream`.

## 6. My Work view

- New `ViewKey` value `'mywork'` (extends the `'board' | 'list' | 'admin' | 'inbox'` union); `WorkOSApp.svelte` routes it to a new `views/MyWorkView.svelte`.
- **Sidebar (D8):** a **My Work** entry at the very top, above the team switcher (it is cross-team and does not depend on `currentWorkstreamId`). Selecting it sets `view='mywork'`.
- **Default landing (D8):** when WorkOS opens, the initial `view` is `'mywork'` instead of `'board'`. Empty state for a user with nothing assigned/created: a friendly "Nothing on your plate yet" message.
- **Store additions:** `myTasks: Writable<Task[]>`, `loadMyWork()` (calls `api.listMyTasks(token)` → `/me/tasks`), plus the live-subscription bookkeeping in §7.
- **Render:** segment toggle (D5) → due-date buckets (D2, via `buckets.ts`) → within each bucket, the shared `FilterBar` result; each row reuses the existing task-row/card rendering and `openTask(id)` for detail. Health chips reuse the existing `progress.ts` logic.
- **Completed work:** My Work shows **open** work — `done` and `canceled` tasks are excluded by default (they would otherwise scatter into `thisWeek`/`later` by their due date). The Status facet can re-include them explicitly when the user wants to see finished items. This default lives in `MyWorkView` (what it passes to `bucketByDueDate`), keeping `buckets.ts` itself a pure, status-agnostic grouping function.

## 7. Realtime — live My Work + sidebar carry-over (D6, D7)

### 7.1 Live My Work (D6)

On entering My Work: `loadMyWork()`, then collect the distinct `workstream_id`s of the returned tasks and **subscribe to each `workos:workstream:{id}` room** (the `workos:subscribe` socket handler gates each join by `can_see_workstream`, so this cannot over-subscribe). Reconcile incoming events into `myTasks`:

- `workos:task.updated` — if the task now matches me (assignee or creator) update/insert it; **if I was just unassigned and am not the creator, remove it.**
- `workos:task.created` — insert if it matches me.
- `workos:task.deleted` — remove.
- **New assignment in a workstream I had no task in** (so I'm not subscribed to its room): the per-user `workos:notification.created` event (type `assigned`/`mentioned`) on my `user:{id}` room triggers a single `getTask(id)` + room-subscribe to fold the task in.

### 7.2 Room ref-counting (the trickiest piece — its own plan task)

My Work subscribing to many workstream rooms must not clobber the board's single active-workstream subscription, and leaving My Work must unsubscribe **only** the rooms My Work added — never the board's active room. Introduce a small reference-counted subscription manager in the store: rooms are entered/left by ref-count, so the board's room survives My Work tearing down its set, and vice versa. This replaces the current ad-hoc "unsubscribe on team change" logic. Reconnect re-subscribes the current active set.

### 7.3 Sidebar carry-over (D7)

The frontend subscribes to `workos:team:{teamId}` for the user's teams and reconciles `workspace.created/updated/deleted` and `workstream.created/updated/deleted` into the `workspaces`/`workstreams` stores, so the sidebar tree updates live (today it only refreshes on manual nav).

**§5 client-side guard (D7 / option A):** per the access-control reference §5, these nav events emit to the **team-wide** room, which can carry metadata of **restricted** workspaces/workstreams to team-only members who shouldn't see them. The client therefore **ignores incoming `*.created` events whose workspace `visibility === 'restricted'`** (it renders only what `/bootstrap` already trimmed). Consequence: a restricted workspace you *are* a member of, created live by someone else, may not appear until your next bootstrap/refresh — an acceptable rare under-show. The proper server-side fix (scope restricted nav events to members, not the team room) is the **tracked §5 follow-up**, deliberately out of this slice.

## 8. Testing

**No DB migration** (read-only endpoint; nothing persisted this slice).

**Backend (TDD, `backend/open_webui/test/workos/`):**
- `/me/tasks` returns tasks assigned to me and tasks created by me, across multiple workstreams/teams.
- **Excludes** a task in a restricted workspace I am not a member of (even if I'm an assignee or the creator) — the visibility filter.
- **Excludes** a task I neither created nor am assigned to.
- De-dupes a task where I am both creator and assignee.
- App-admin scoping behaves consistently.

**Frontend (vitest, `src/lib/components/workos/`):**
- `filters.ts`: each facet, empty-filter identity, combined facets, text match on title + key (case-insensitive), empty text.
- `buckets.ts`: overdue / today boundary / this-week boundary / later / null-due — with injected `now`.
- Segment logic: All / Assigned / Created derivation from `created_by_id` + `assignee_ids`.
- Store reconciliation: live add on new match, **remove on unassign**, delete; ref-counting (entering/leaving My Work does not drop the board's room).

## 9. Files touched (anticipated)

**Backend**
- `models/workos.py` — `Tasks.list_for_user(user_id, team_ids)`.
- `routers/workos.py` — `GET /me/tasks` handler with the `can_see_workstream` filter + de-dup.
- `docs/superpowers/specs/2026-06-26-workos-access-control.md` — §4 endpoint row (standing rule).

**Frontend** (`src/lib/components/workos/`)
- `lib/api.ts` — `listMyTasks(token)`.
- `lib/store.ts` — `myTasks`, `loadMyWork()`, ref-counted room manager, `'mywork'` view, default-landing change, team-room subscription + sidebar reconcilers.
- `lib/types.ts` — `TaskFilter`, due-date bucket types, `ViewKey` extension.
- `lib/filters.ts`, `lib/buckets.ts` — new pure engines.
- `chrome/FilterBar.svelte` — new shared bar (replaces BoardView placeholders).
- `chrome/Sidebar.svelte` — My Work entry.
- `views/MyWorkView.svelte` — new view (segment + buckets + FilterBar).
- `views/BoardView.svelte`, `views/ListView.svelte` — mount FilterBar, apply `applyFilters`.
- `WorkOSApp.svelte` — route `'mywork'`.

## 10. Risks & follow-ups

- **Room ref-counting (§7.2)** is the highest-risk change — it reworks existing subscribe/unsubscribe logic. Isolated as its own plan task with dedicated tests; a regression could silently drop the board's live updates.
- **`/me/tasks` performance (§4.2)** — candidate-by-team + Python filter is fine for current scale; large teams are a known future optimization (assignee index), explicitly deferred.
- **§5 server-side nav-room scoping (§7.3)** — remains a tracked residual in the access-control doc; this slice mitigates client-side only.
- **No deep-linking** — My Work rows open the existing in-page detail overlay; URL routing is a separate deferred slice.

## 11. References

- Access control (source of truth): `docs/superpowers/specs/2026-06-26-workos-access-control.md` ([workos-access-control] standing rule).
- Phase 2 design: `docs/superpowers/specs/2026-06-24-workos-phase2-design.md`.
- Memories: [workos-phase1], [workos-phase2], [workos-multi-assignee], [workos-access-control].
