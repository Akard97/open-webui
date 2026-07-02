<!--
  WorkOS — Access Control Hardening: design spec for closing the 11 verified gaps
  documented in 2026-06-26-workos-access-control.md §8. Branch `osool`.
  Companion to the reference doc — KEEP BOTH IN SYNC. When a gap below lands,
  update the reference doc's §8 (mark closed) and the §3/§4/§5/§7 tables.
-->

# WorkOS — Access Control Hardening (Design)

> Closes all 11 verified gaps (G1–G11) from [the access-control reference §8](2026-06-26-workos-access-control.md). Single spec, three ordered workstreams sharing two new helpers. No DB migration.

## 1. Context & goal

The [WorkOS access-control audit](2026-06-26-workos-access-control.md) found 11 verified gaps. The root theme is **assignment/participation treated as access**: several code paths push task metadata (and comment text) to people who cannot open the task. The [§9 decision (2026-06-26)](2026-06-26-workos-access-control.md) — *no per-workstream visibility; confidentiality rests entirely on restricted Workspaces* — makes the leak gaps higher priority, because they partially defeat a restricted Workspace via assignment and the per-user notification channel.

Goal: close all 11 gaps, ordered by severity, without a schema migration and without breaking the intended add-member flow.

## 2. Decisions (settled with the user, 2026-06-27)

1. **Write policy for tasks/subtasks (G2/G5/G6): lock to creator / assignee / workspace-manager.** Editing a task requires being its creator, an assignee, or a workspace owner/admin (or a global app-admin). Subtask edit/delete additionally allows the subtask's own author.
2. **Roster exposure (G7): restrict `GET /users` to team owners/admins.** The endpoint takes a `team_id` and is gated by `require_team_role({'owner','admin'})`. This keeps the "Add a user…" picker working (it is always invoked in a team context) while narrowing name-enumeration to the people who actually manage membership.
3. **Structure: one spec, three workstreams, phased implementation** (leaks → write gates → hardening), sharing two new helpers.

### 2a. Deliberate refinement (confirmed 2026-06-27)
The user's write-policy answer named "edit/complete/**delete**." Applied precisely, and confirmed with the user that **deletion is narrower than editing**:
- **Task *edit* (`PATCH /tasks`)** → creator / assignee / workspace-manager / admin. *(new — G2)*
- **Task *deletion* (`DELETE /tasks`)** → **unchanged**: creator / team owner-admin / admin. Already gated ([workos.py:684–686](../../../backend/open_webui/routers/workos.py:684)); it is **not** one of the 11 gaps. Assignees can edit a task and manage its subtasks but **cannot delete the entire task**. Confirmed: deletion stays stricter than editing.
- **Subtask edit & delete (`PATCH`/`DELETE /subtasks`)** → subtask author / parent-task creator / parent-task assignee / workspace-manager / admin. *(new — G5, G6)*

## 3. Non-goals

- Per-workstream visibility (explicitly declined in [§9](2026-06-26-workos-access-control.md)).
- Evicting live sockets on membership revocation (the §5 "no eviction on revocation" caveat — a known residual, out of scope here).
- The §5 "structural scoping mismatch" (workspace/workstream metadata events emitted to the team-wide room). Tracked separately; not in the G1–G11 set.
- Any DB schema change. All gates use existing columns (`created_by_id`, `assignee_ids`, membership tables).

## 4. Shared helpers (built once, reused)

Two new helpers in `backend/open_webui/routers/workos.py` carry most of the work:

### 4a. `_recipient_is_admin(uid, db)` + recipient visibility filter
A small resolver returning whether a recipient user id is a global app-admin (`Users.get_user_by_id(uid).role == 'admin'`, missing → `False`). Used to call `can_see_workstream(uid, is_admin, workstream_id, db=db)` per recipient.

### 4b. `_is_workspace_manager(user, workspace, db)`
Extracted from the existing `require_workspace_manage` tail ([workos.py:320–324](../../../backend/open_webui/routers/workos.py:320)): `True` if `team_role ∈ {'owner','admin'}` OR the user's `WorkspaceMembers` row has `role == 'admin'`. Reused by both write-gate helpers below so the "manager" definition stays single-sourced.

---

## 5. Workstream 1 — Close the leaks (G1, G3, G4) · HIGH

### 5a. Centralize recipient filtering inside `notify()` → closes G3 + G4
`notify()` ([workos.py:817](../../../backend/open_webui/routers/workos.py:817)) already receives the `task`, and `task.workstream_id` is on it. After building `targets` (line 823), filter every recipient through `can_see_workstream`:

```python
targets = {r for r in recipients if r and r != actor.id}
visible = set()
for uid in targets:
    is_admin = await _recipient_is_admin(uid, db)
    if await can_see_workstream(uid, is_admin, task.workstream_id, db=db):
        visible.add(uid)
targets = visible
if not targets:
    return []
```

This makes **every** notification path leak-safe by construction:
- **G3** — `assigned` ([workos.py:630](../../../backend/open_webui/routers/workos.py:630), [:669](../../../backend/open_webui/routers/workos.py:669)) and `status_changed` ([:671–673](../../../backend/open_webui/routers/workos.py:671)) can no longer reach a non-member assignee or a creator who has since lost visibility.
- **G4** — `commented` to `_participants(task)` ([:894–896](../../../backend/open_webui/routers/workos.py:894)) — including the 140-char snippet ([:830–831](../../../backend/open_webui/routers/workos.py:830)) — is filtered, so historical mentioners who lost access stop receiving comment text.

The existing explicit mention filter in `create_comment` ([:888–891](../../../backend/open_webui/routers/workos.py:888)) **stays** (it also computes the `mentioned` set used to subtract from `participants`); `notify()`'s filter is now the universal backstop.

*Perf note:* per-recipient role lookup is N small queries (N = assignees/participants, typically < 10). Acceptable; a batched `Users` fetch is a future optimization, not required.

### 5b. Validate `assignee_ids` against visibility → closes G1
New helper:

```python
async def _validate_assignees(assignee_ids, workstream_id, db):
    for uid in assignee_ids or []:
        is_admin = await _recipient_is_admin(uid, db)
        if not await can_see_workstream(uid, is_admin, workstream_id, db=db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='One or more assignees cannot access this workstream.',
            )
```

- **`create_task`** ([workos.py:614](../../../backend/open_webui/routers/workos.py:614)): call before `Tasks.insert`, using `workstream_id`.
- **`update_task`** ([workos.py:643](../../../backend/open_webui/routers/workos.py:643)): when `'assignee_ids' in fields`, call before `Tasks.update_fields`, using `task.workstream_id`.

**Reject (400)**, consistent with the locked-down policy: an assignee who cannot see the task is a data-model error, not just a notification artifact. The picker (§7) offers only eligible users, so this is a guard against forged/stale ids.

---

## 6. Workstream 2 — Write gates (G2, G5, G6) · MEDIUM/HIGH

### 6a. `require_task_writable` → closes G2
```python
async def require_task_writable(user, task, stream, db):
    if user.role == 'admin':
        return
    if task.created_by_id == user.id:
        return
    if user.id in (task.assignee_ids or []):
        return
    ws = await Workspaces.get_by_id(stream.workspace_id, db=db)
    if await _is_workspace_manager(user, ws, db):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                        detail='You do not have permission to edit this task.')
```
Applied in `update_task` ([workos.py:643](../../../backend/open_webui/routers/workos.py:643)) immediately after `require_task_visible` returns `(task, stream)`, before `Tasks.update_fields`.

### 6b. `require_subtask_writable` → closes G5 + G6
```python
async def require_subtask_writable(user, subtask, task, stream, db):
    if user.role == 'admin':
        return
    if subtask.created_by_id == user.id:
        return
    if task.created_by_id == user.id or user.id in (task.assignee_ids or []):
        return
    ws = await Workspaces.get_by_id(stream.workspace_id, db=db)
    if await _is_workspace_manager(user, ws, db):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                        detail='You do not have permission to modify this subtask.')
```
`require_subtask_visible` ([workos.py:1086](../../../backend/open_webui/routers/workos.py:1086)) already returns `(subtask, task, stream)`. Apply the gate in:
- `update_subtask` ([workos.py:1128](../../../backend/open_webui/routers/workos.py:1128)) — before `Subtasks.update_fields`. *(G5)*
- `delete_subtask` ([workos.py:1155](../../../backend/open_webui/routers/workos.py:1155)) — before `Subtasks.delete`. *(G6)*

### 6c. Frontend (cosmetic only — backend is the gate)
Add pure predicates to `src/lib/components/workos/lib/roles.ts` mirroring the backend rule and use them to show/hide edit controls; no security relies on them:
- `canEditTask(task, userId, teamRole, workspaceRole)` → creator || assignee || manager || admin.
- `canEditSubtask(subtask, task, …)` → subtask author || the task rule above.

The existing dead `canManageWorkspace` predicate ([noted in §6 of the reference](2026-06-26-workos-access-control.md)) is a candidate to wire up or remove while here.

---

## 7. Workstream 3 — Hardening (G7–G11) · LOW/MEDIUM

### G7 — scope `GET /users` to team owners/admins
[workos.py:148–154](../../../backend/open_webui/routers/workos.py:148). Add a **required** `team_id` query param and gate:
```python
@router.get('/users')
async def list_users(request, team_id: str, user=…, db=…):
    await _require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner', 'admin'})
    return await list_all_users()
```
**Contract change.** Frontend: `api.listUsers(teamId)` in `src/lib/components/workos/lib/api.ts` and its single caller (the team "Add a user…" picker) must pass the current team id. Confirm during implementation that this is the **only** caller (see §10 open items).

### G8 — apply `default_workspace_visibility`
[create_workspace workos.py:344–357](../../../backend/open_webui/routers/workos.py:344). Make `WorkspaceForm.visibility` optional (default `None`); when unset, fall back to the configured rule:
```python
rules = request.app.state.config.WORKOS_RULES or {}
visibility = form.visibility or rules.get('default_workspace_visibility') or 'team'
if visibility not in {'team', 'restricted'}:
    raise HTTPException(400, 'Invalid visibility.')
```
Now the advertised [`WORKOS_RULES.default_workspace_visibility`](2026-06-26-workos-access-control.md) actually takes effect. Update the reference §7 table (was "validated but NOT consumed").

### G9 — last-owner guard
[remove_member workos.py:271–278](../../../backend/open_webui/routers/workos.py:271) and [update_member :255–268](../../../backend/open_webui/routers/workos.py:255). New helper:
```python
async def _is_last_owner(team_id, user_id, db):
    members = await TeamMembers.list_for_team(team_id, db=db)
    owners = [m for m in members if m.role == 'owner']
    return len(owners) == 1 and owners[0].user_id == user_id
```
- `remove_member`: if the target `_is_last_owner`, reject `400 'Cannot remove the last team owner.'`
- `update_member`: if demoting (target currently owner, `form.role != 'owner'`) and `_is_last_owner`, reject `400 'Cannot demote the last team owner.'`

### G10 — clamp notification paging
[list_notifications workos.py:1064–1070](../../../backend/open_webui/routers/workos.py:1064): `limit = max(1, min(limit, 200))` before passing to the DAO. (Leave `before` as-is; it is an opaque cursor.)

### G11 — attachment MIME allowlist + comment ownership
[upload_attachment workos.py:967–995](../../../backend/open_webui/routers/workos.py:967):
1. **Comment ownership:** if `comment_id` is provided, fetch `Comments.get_by_id(comment_id)`; reject `400` if missing or `comment.task_id != task_id`.
2. **MIME allowlist (confirmed):** reject `file.content_type` not in a module-level `ATTACHMENT_MIME_ALLOW` set. Starting contents: `image/png`, `image/jpeg`, `image/gif`, `image/webp`, `image/svg+xml`, `application/pdf`, the common office types (`application/msword`, `application/vnd.openxmlformats-officedocument.*` for docx/xlsx/pptx, `application/vnd.ms-excel`, `application/vnd.ms-powerpoint`), `text/plain`, `text/csv`, `text/markdown`, `application/json`, `application/zip`. Reject anything else with `400`. Exact contents are tunable during implementation; the allowlist approach itself is settled.

---

## 8. Cross-cutting

- **Tests (TDD).** Every gap gets a failing test first, then the fix. Suite lives in `backend/open_webui/test/workos/` (e.g. the already-touched `test_router_directory.py`). Coverage per gap:
  - G1: assign a non-visible user → 400; assign a visible team member → 200.
  - G3/G4: notify a recipient who can't see the workstream → no row, no emit; visible recipient → row + emit. (Assert at the `notify()` level and via the comment/assign endpoints.)
  - G2/G5/G6: non-creator/non-assignee/non-manager edit → 403; each allowed principal → 200.
  - G7: non-owner/admin caller → 403; owner/admin → roster; missing `team_id` → 422.
  - G8: rule `restricted` + form unset → workspace created `restricted`.
  - G9: remove/demote last owner → 400; with a second owner present → 200.
  - G10: `limit=99999` → DAO receives 200.
  - G11: foreign `comment_id` → 400; disallowed MIME → 400.
- **No migration.** Confirmed: `WorkosSubtask.created_by_id` ([models/workos.py:490](../../../backend/open_webui/models/workos.py:490)), `WorkosTask.assignee_ids`/`created_by_id`, and membership tables already exist.
- **Reference-doc update (standing rule).** After the fixes land, update [2026-06-26-workos-access-control.md](2026-06-26-workos-access-control.md): mark §8 G1–G11 closed, refresh §3/§4 (new helpers + the `/users`, `PATCH /tasks`, `PATCH`/`DELETE /subtasks` rows), §5 (notify now filters recipients), §7 (`default_workspace_visibility` now consumed).

## 9. Implementation order (phases)

| Phase | Gaps | Why first |
|---|---|---|
| **1 — Leaks** | G1, G3, G4 | Highest severity; pure security upside; builds `_recipient_is_admin` + the `notify()` filter + `_validate_assignees`. |
| **2 — Write gates** | G2, G5, G6 | Builds `_is_workspace_manager`, `require_task_writable`, `require_subtask_writable` + frontend predicates. |
| **3 — Hardening** | G7, G8, G9, G10, G11 | Independent, low-risk; G7 carries a frontend contract change. |
| **4 — Docs** | — | Update the reference doc to reflect closed gaps. |

Each phase is independently testable and reviewable; phases can land as separate commits/PRs under one branch.

## 10. Risks & open items (resolve during implementation)

1. **G7 frontend ripple.** Confirm the team "Add a user…" picker is the *only* caller of `api.listUsers`; if anything else consumes the full roster without a team context, it needs rework or a different gate.
2. **`notify()` per-recipient role lookup** is N queries; fine at current scale, batch later if needed.
3. **`Users` accessor name.** Use the canonical `Users.get_user_by_id` (sync) already used elsewhere in the app; verify import in `workos.py` during implementation.

*Settled (no longer open):* task-delete stays creator/manager-only (§2a, confirmed); G11 ships the MIME allowlist (§7, confirmed).

## 11. Verification

- Run the WorkOS backend suite with the project `.venv` python (the suite needs the venv interpreter on this box): `pytest backend/open_webui/test/workos -q`. All new + existing tests green.
- Manual smoke (recommended, not blocking): (a) try to assign a user who can't see a restricted workspace → blocked; (b) a non-assignee team member tries to edit a task they don't own → edit controls hidden, API 403; (c) add-member picker still lists users for an owner/admin; (d) last-owner removal blocked.

---

## 12. Addendum (2026-07-02) — realtime non-goals implemented

The two realtime items this design explicitly left out of scope were implemented on 2026-07-02, alongside a predicate consolidation:

- **Socket eviction on membership revocation** — `remove_member` / `remove_workspace_member` now drop the removed user's live sockets from the rooms the removal makes invisible (`workos_leave_rooms` in socket/main.py, best-effort `evict_user` wrapper in the router).
- **Structural scoping mismatch** — workspace/workstream nav events are visibility-routed (`_emit_nav_event`): restricted-workspace events go to member `user:{id}` rooms, never the team-wide room; team↔restricted visibility flips emit an ordered rebuild sequence plus room eviction.
- Also: `workos:subscribe` now authorizes from the connection's `SESSION_POOL` identity (payload tokens ignored), access predicates live in `backend/open_webui/utils/workos_access.py`, and member-role strings are validated at the DAO layer.

See the reference doc (2026-06-26-workos-access-control.md) §2/§3/§5 for the current state.
