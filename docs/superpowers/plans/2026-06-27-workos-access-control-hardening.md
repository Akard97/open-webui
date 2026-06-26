# WorkOS Access-Control Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all 11 verified access-control gaps (G1–G11) from the [WorkOS access-control audit](../specs/2026-06-26-workos-access-control.md) without a DB migration.

**Architecture:** Almost all work lives in one file, `backend/open_webui/routers/workos.py`, plus targeted test files. Two new helpers carry most of it: a recipient-visibility filter inside `notify()` (closes G3+G4 in one place) and `_is_workspace_manager` (single-sources the "manager" rule for the new write gates). Three ordered workstreams: **leaks → write gates → hardening**, then a docs pass.

**Tech Stack:** Python / FastAPI / SQLAlchemy async; pytest + httpx ASGITransport for the backend; SvelteKit + vitest for the (cosmetic) frontend predicates.

## Global Constraints

- **No DB schema migration.** All gates use existing columns: `WorkosTask.assignee_ids`, `WorkosTask.created_by_id`, `WorkosSubtask.created_by_id`, and the team/workspace membership tables.
- **Write policy (confirmed):** task *edit* = creator OR assignee OR workspace-manager OR global admin. Task *deletion* stays unchanged (creator OR team owner/admin OR admin — narrower than edit, by decision). Subtask edit/delete = subtask author OR parent-task creator/assignee OR workspace-manager OR admin.
- **Roster (G7, confirmed):** `GET /users` requires a `team_id` and is gated to team owners/admins.
- **Attachments (G11, confirmed):** ship a MIME allowlist; reject anything not on it.
- **Visibility helper signature:** `can_see_workstream(user_id, is_admin, workstream_id, db=db)` — non-raising bool ([models/workos.py:1108](../../../backend/open_webui/models/workos.py:1108)).
- **Test interpreter:** run the backend suite with the project `.venv` python (this box needs the venv interpreter).
- **Tests are TDD:** write the failing test, watch it fail, implement, watch it pass, commit — every task.
- **Reference doc:** after the code lands, update [../specs/2026-06-26-workos-access-control.md](../specs/2026-06-26-workos-access-control.md) (standing rule).

---

## File Structure

- `backend/open_webui/routers/workos.py` — all backend gate logic (helpers + endpoint edits).
- `backend/open_webui/test/workos/test_router_access_leaks.py` — **new**: G1/G3/G4 tests.
- `backend/open_webui/test/workos/test_router_write_gates.py` — **new**: G2/G5/G6 tests.
- `backend/open_webui/test/workos/test_router_hardening.py` — **new**: G7/G8/G9/G10/G11 tests.
- `backend/open_webui/test/workos/test_router_multi_assignee.py` — **modify**: seed membership in its `_task` helper (G1 ripple).
- `backend/open_webui/test/workos/test_router_directory.py` — **modify**: rewrite the two `/users` tests to the gated contract (G7).
- `backend/open_webui/test/workos/test_router_teams.py` — **modify**: extend `_make_app`/`_client` with an optional `rules=` arg (G8 needs custom `WORKOS_RULES`).
- `src/lib/components/workos/lib/roles.ts` + `roles.test.ts` — **modify**: add `canEditTask`/`canEditSubtask` predicates (cosmetic).
- `src/lib/components/workos/lib/api.ts` + `views/ModalHost.svelte` — **modify**: `listAllUsers(token, teamId)` (G7 frontend).

---

# Phase 1 — Close the leaks (G1, G3, G4)

## Task 1: Centralized recipient-visibility filter in `notify()` (G3 + G4)

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (add `Users` import; add `_recipient_is_admin`; filter inside `notify` at [:817](../../../backend/open_webui/routers/workos.py:817))
- Test: `backend/open_webui/test/workos/test_router_access_leaks.py` (create)

**Interfaces:**
- Produces: `async _recipient_is_admin(uid: str, db) -> bool`; `notify()` now drops any recipient failing `can_see_workstream`.
- Consumes: existing `can_see_workstream`, `Users.get_user_by_id(id, db=db)` (async, returns `None` on missing/error).

- [ ] **Step 1: Write the failing tests**

Create `backend/open_webui/test/workos/test_router_access_leaks.py`:

```python
import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1, U2


async def _restricted_task(c):
    """U1 owns a restricted workspace (auto workspace-admin) with one stream + task."""
    team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                       json={'name': 'Eng', 'visibility': 'restricted'})).json()
    s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'P'})).json()
    t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'T'})).json()
    return team, ws, s, t


@pytest.mark.asyncio
async def test_commented_notification_skips_participant_who_lost_visibility(monkeypatch):
    sent = []

    async def _eu(event, payload, user_ids):
        if payload.get('type') == 'commented':
            sent.extend(user_ids)

    monkeypatch.setattr(wr, 'emit_users', _eu)
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, t = await _restricted_task(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        await c.post(f"/api/v1/workos/workspaces/{ws['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c2:
        # u2 can see the stream now, so becomes a comment participant.
        await c2.post(f"/api/v1/workos/tasks/{t['id']}/comments", json={'body': 'u2 here'})
    async with _client(monkeypatch, user=U1) as c:
        await c.delete(f"/api/v1/workos/workspaces/{ws['id']}/members/u2")  # u2 loses visibility
        await c.post(f"/api/v1/workos/tasks/{t['id']}/comments", json={'body': 'reply'})
    assert 'u2' not in sent


@pytest.mark.asyncio
async def test_commented_notification_reaches_visible_participant(monkeypatch):
    sent = []

    async def _eu(event, payload, user_ids):
        if payload.get('type') == 'commented':
            sent.extend(user_ids)

    monkeypatch.setattr(wr, 'emit_users', _eu)
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, t = await _restricted_task(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        await c.post(f"/api/v1/workos/workspaces/{ws['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c2:
        await c2.post(f"/api/v1/workos/tasks/{t['id']}/comments", json={'body': 'u2 here'})
    async with _client(monkeypatch, user=U1) as c:
        await c.post(f"/api/v1/workos/tasks/{t['id']}/comments", json={'body': 'reply'})
    assert 'u2' in sent
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/open_webui/test/workos/test_router_access_leaks.py -v`
Expected: `test_commented_notification_skips_participant_who_lost_visibility` FAILS (`'u2'` still notified — no filter yet).

- [ ] **Step 3: Add the `Users` import**

In `backend/open_webui/routers/workos.py`, after the existing model import block ([:15-21](../../../backend/open_webui/routers/workos.py:15)), add:

```python
from open_webui.models.users import Users
```

- [ ] **Step 4: Add `_recipient_is_admin` and filter inside `notify()`**

Add the helper just above `notify` ([:817](../../../backend/open_webui/routers/workos.py:817)):

```python
async def _recipient_is_admin(uid: str, db) -> bool:
    u = await Users.get_user_by_id(uid, db=db)
    return bool(u and u.role == 'admin')
```

Inside `notify`, replace the target-building block (currently [:823-825](../../../backend/open_webui/routers/workos.py:823)):

```python
    targets = {r for r in recipients if r and r != actor.id}
    if not targets:
        return []
```

with:

```python
    targets = {r for r in recipients if r and r != actor.id}
    visible = set()
    for uid in targets:
        if await can_see_workstream(uid, await _recipient_is_admin(uid, db), task.workstream_id, db=db):
            visible.add(uid)
    targets = visible
    if not targets:
        return []
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest backend/open_webui/test/workos/test_router_access_leaks.py -v`
Expected: both tests PASS.

- [ ] **Step 6: Run the full workos suite (regression guard)**

Run: `pytest backend/open_webui/test/workos -q`
Expected: all green except (possibly) `test_router_multi_assignee.py` — that file is fixed in Task 2. If anything else fails, stop and investigate.

- [ ] **Step 7: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_access_leaks.py
git commit -m "fix(workos): filter notification recipients by workstream visibility (G3, G4)"
```

---

## Task 2: Validate `assignee_ids` against visibility (G1)

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (`_validate_assignees`; call in `create_task` [:614](../../../backend/open_webui/routers/workos.py:614) and `update_task` [:643](../../../backend/open_webui/routers/workos.py:643))
- Modify: `backend/open_webui/test/workos/test_router_multi_assignee.py` (seed membership in `_task`)
- Test: `backend/open_webui/test/workos/test_router_access_leaks.py` (append)

**Interfaces:**
- Consumes: `_recipient_is_admin` (Task 1), `can_see_workstream`.
- Produces: `async _validate_assignees(assignee_ids, workstream_id, db)` — raises `400` if any id can't see the workstream.

- [ ] **Step 1: Write the failing tests**

Append to `backend/open_webui/test/workos/test_router_access_leaks.py`:

```python
from open_webui.test.workos.test_router_task import _stream


@pytest.mark.asyncio
async def test_create_task_rejects_assignee_who_cannot_see_workstream(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)  # team-visible; u2 is NOT a member
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                         json={'title': 'T', 'assignee_ids': ['u2']})
        assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_create_task_allows_assignee_who_is_team_member(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                         json={'title': 'T', 'assignee_ids': ['u2']})
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_update_task_rejects_unseeable_assignee(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'T'})).json()
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u2']})
        assert r.status_code == 400, r.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/open_webui/test/workos/test_router_access_leaks.py -k assignee -v`
Expected: the two "rejects" tests FAIL (currently return 200).

- [ ] **Step 3: Add `_validate_assignees` and call it**

Add the helper just above `create_task` ([:614](../../../backend/open_webui/routers/workos.py:614)):

```python
async def _validate_assignees(assignee_ids, workstream_id, db):
    for uid in assignee_ids or []:
        if not await can_see_workstream(uid, await _recipient_is_admin(uid, db), workstream_id, db=db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='One or more assignees cannot access this workstream.',
            )
```

In `create_task`, immediately before `task = await Tasks.insert(` ([:623](../../../backend/open_webui/routers/workos.py:623)):

```python
    await _validate_assignees(form.assignee_ids, workstream_id, db)
```

In `update_task`, immediately after the `_validate_task_fields(fields, ...)` line ([:651](../../../backend/open_webui/routers/workos.py:651)):

```python
    if 'assignee_ids' in fields:
        await _validate_assignees(fields['assignee_ids'], task.workstream_id, db)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/open_webui/test/workos/test_router_access_leaks.py -k assignee -v`
Expected: all three PASS.

- [ ] **Step 5: Fix the multi-assignee suite (G1 ripple)**

Its `_task` helper assigns `u2`/`u3` who aren't members. Update the helper in `backend/open_webui/test/workos/test_router_multi_assignee.py` ([:8-12](../../../backend/open_webui/test/workos/test_router_multi_assignee.py:8)) to seed them as members first:

```python
async def _task(c, **body):
    team, ws, s = await _stream(c)
    for uid in ('u2', 'u3'):
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': uid, 'role': 'member'})
    t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                      json={'title': 'T', **body})).json()
    return team, ws, s, t
```

- [ ] **Step 6: Run the multi-assignee suite + the leaks suite**

Run: `pytest backend/open_webui/test/workos/test_router_multi_assignee.py backend/open_webui/test/workos/test_router_access_leaks.py -v`
Expected: all PASS (every assignment now targets a team member).

- [ ] **Step 7: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_access_leaks.py backend/open_webui/test/workos/test_router_multi_assignee.py
git commit -m "fix(workos): reject assignees who cannot see the workstream (G1)"
```

---

# Phase 2 — Write gates (G2, G5, G6)

## Task 3: `require_task_writable` on `PATCH /tasks` (G2)

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (`_is_workspace_manager`; refactor `require_workspace_manage` [:318](../../../backend/open_webui/routers/workos.py:318); add `require_task_writable`; apply in `update_task` [:643](../../../backend/open_webui/routers/workos.py:643))
- Test: `backend/open_webui/test/workos/test_router_write_gates.py` (create)

**Interfaces:**
- Produces: `async _is_workspace_manager(user, workspace, db) -> bool`; `async require_task_writable(user, task, stream, db)` (raises `403`).
- Consumes: existing `team_role`, `WorkspaceMembers.get`, `Workspaces.get_by_id`.

- [ ] **Step 1: Write the failing tests**

Create `backend/open_webui/test/workos/test_router_write_gates.py`:

```python
import pytest

from open_webui.test.workos.test_router_teams import _client, U1, U2
from open_webui.test.workos.test_router_task import _stream


@pytest.mark.asyncio
async def test_member_cannot_edit_task_they_dont_own(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'T'})).json()
    async with _client(monkeypatch, user=U2) as c:
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'title': 'hijack'})
        assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_assignee_can_edit_task(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                          json={'title': 'T', 'assignee_ids': ['u2']})).json()
    async with _client(monkeypatch, user=U2) as c:
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'in_progress'})
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_team_admin_can_edit_others_task(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'admin'})
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'T'})).json()
    async with _client(monkeypatch, user=U2) as c:
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'title': 'edited'})
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_creator_can_still_edit_own_task(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'T'})).json()
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'priority': 'high'})
        assert r.status_code == 200, r.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/open_webui/test/workos/test_router_write_gates.py -v`
Expected: `test_member_cannot_edit_task_they_dont_own` FAILS (currently 200).

- [ ] **Step 3: Extract `_is_workspace_manager` and refactor `require_workspace_manage`**

In `backend/open_webui/routers/workos.py`, replace `require_workspace_manage` ([:318-325](../../../backend/open_webui/routers/workos.py:318)) with:

```python
async def _is_workspace_manager(user, workspace, db: AsyncSession) -> bool:
    if (await team_role(user, workspace.team_id, db)) in {'owner', 'admin'}:
        return True
    wm = await WorkspaceMembers.get(workspace.id, user.id, db=db)
    return bool(wm and wm.role == 'admin')


async def require_workspace_manage(user, workspace_id: str, db: AsyncSession):
    ws = await require_workspace_visible(user, workspace_id, db)
    if await _is_workspace_manager(user, ws, db):
        return ws
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Workspace management requires admin.')
```

- [ ] **Step 4: Add `require_task_writable` and apply it**

Add near the task helpers (just above `create_task`, after `_validate_assignees`):

```python
async def require_task_writable(user, task, stream, db: AsyncSession) -> None:
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

In `update_task` ([:649](../../../backend/open_webui/routers/workos.py:649)), change the visibility line to keep the stream and add the gate:

```python
    task, stream = await require_task_visible(user, task_id, db)
    await require_task_writable(user, task, stream, db)
```

(Replaces the current `task, _ = await require_task_visible(user, task_id, db)`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest backend/open_webui/test/workos/test_router_write_gates.py -v`
Expected: all four PASS.

- [ ] **Step 6: Regression guard**

Run: `pytest backend/open_webui/test/workos -q`
Expected: all green. (Existing task/multi-assignee patches act as the creator U1, so they remain writable.)

- [ ] **Step 7: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_write_gates.py
git commit -m "fix(workos): gate task edits to creator/assignee/manager (G2)"
```

---

## Task 4: `require_subtask_writable` on `PATCH`/`DELETE /subtasks` (G5, G6)

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (`require_subtask_writable`; apply in `update_subtask` [:1128](../../../backend/open_webui/routers/workos.py:1128) and `delete_subtask` [:1155](../../../backend/open_webui/routers/workos.py:1155))
- Test: `backend/open_webui/test/workos/test_router_write_gates.py` (append)

**Interfaces:**
- Consumes: `_is_workspace_manager` (Task 3); `require_subtask_visible` already returns `(subtask, task, stream)`.
- Produces: `async require_subtask_writable(user, subtask, task, stream, db)` (raises `403`).

- [ ] **Step 1: Write the failing tests**

Append to `backend/open_webui/test/workos/test_router_write_gates.py`:

```python
async def _subtask(c):
    team, ws, s = await _stream(c)
    t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'T'})).json()
    st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks", json={'title': 'sub'})).json()
    return team, ws, s, t, st


@pytest.mark.asyncio
async def test_member_cannot_edit_others_subtask(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, t, st = await _subtask(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c:
        r = await c.patch(f"/api/v1/workos/subtasks/{st['id']}", json={'completed': True})
        assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_member_cannot_delete_others_subtask(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, t, st = await _subtask(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c:
        r = await c.delete(f"/api/v1/workos/subtasks/{st['id']}")
        assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_task_creator_can_modify_and_delete_subtask(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, t, st = await _subtask(c)
        r = await c.patch(f"/api/v1/workos/subtasks/{st['id']}", json={'completed': True})
        assert r.status_code == 200, r.text
        r = await c.delete(f"/api/v1/workos/subtasks/{st['id']}")
        assert r.json()['deleted'] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/open_webui/test/workos/test_router_write_gates.py -k subtask -v`
Expected: the two "cannot" tests FAIL (currently 200).

- [ ] **Step 3: Add `require_subtask_writable`**

Add just above `update_subtask` ([:1128](../../../backend/open_webui/routers/workos.py:1128)):

```python
async def require_subtask_writable(user, subtask, task, stream, db: AsyncSession) -> None:
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

- [ ] **Step 4: Apply it in both handlers**

In `update_subtask` ([:1134](../../../backend/open_webui/routers/workos.py:1134)), change:

```python
    subtask, task, _ = await require_subtask_visible(user, subtask_id, db)
```
to:
```python
    subtask, task, stream = await require_subtask_visible(user, subtask_id, db)
    await require_subtask_writable(user, subtask, task, stream, db)
```

In `delete_subtask` ([:1160](../../../backend/open_webui/routers/workos.py:1160)), make the identical change.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest backend/open_webui/test/workos/test_router_write_gates.py -k subtask -v`
Expected: all three PASS.

- [ ] **Step 6: Regression guard + commit**

Run: `pytest backend/open_webui/test/workos -q` (expect all green), then:

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_write_gates.py
git commit -m "fix(workos): gate subtask edit/delete to author/task-owner/manager (G5, G6)"
```

---

## Task 5: Frontend edit predicates (cosmetic) (G2/G5/G6 UI)

**Files:**
- Modify: `src/lib/components/workos/lib/roles.ts`
- Test: `src/lib/components/workos/lib/roles.test.ts`

**Interfaces:**
- Produces: `canEditTask(task, userId, teamRole, workspaceRole)` and `canEditSubtask(subtask, task, userId, teamRole, workspaceRole)` — pure booleans mirroring the backend gate.
- Note: these are **cosmetic** (show/hide affordances). The backend (Tasks 3–4) is the real enforcement. Wiring them into the many `editing*` affordances inside `TaskDetail.svelte` is intentionally **deferred polish** (see "Deferred / out of scope" below) — this task ships only the tested predicate layer.

- [ ] **Step 1: Write the failing tests**

In `src/lib/components/workos/lib/roles.test.ts`, add `canEditTask, canEditSubtask` to the import ([:2-4](../../../src/lib/components/workos/lib/roles.test.ts:2)), add `assignee_ids: []` to the `task` factory defaults ([:9](../../../src/lib/components/workos/lib/roles.test.ts:9)), and append inside the `describe('roles', …)` block:

```ts
	it('task editing: creator, assignee, or workspace manager', () => {
		expect(canEditTask(task({ created_by_id: 'u1' }), 'u1', 'member', undefined)).toBe(true);
		expect(canEditTask(task({ created_by_id: 'u9', assignee_ids: ['u1'] }), 'u1', 'member', undefined)).toBe(true);
		expect(canEditTask(task({ created_by_id: 'u9', assignee_ids: [] }), 'u1', 'member', 'member')).toBe(false);
		expect(canEditTask(task({ created_by_id: 'u9' }), 'u1', 'admin', undefined)).toBe(true);
	});
	it('subtask editing: subtask author or task editor', () => {
		expect(canEditSubtask({ created_by_id: 'u1' }, task({ created_by_id: 'u9' }), 'u1', 'member', undefined)).toBe(true);
		expect(canEditSubtask({ created_by_id: 'u9' }, task({ created_by_id: 'u9' }), 'u1', 'member', undefined)).toBe(false);
	});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/lib/components/workos/lib/roles.test.ts`
Expected: FAIL — `canEditTask`/`canEditSubtask` are not exported.

- [ ] **Step 3: Implement the predicates**

Append to `src/lib/components/workos/lib/roles.ts`:

```ts
export function canEditTask(
	task: Task,
	userId: string,
	teamRole: TeamRole | undefined,
	workspaceRole: WorkspaceRole | undefined
): boolean {
	return (
		task.created_by_id === userId ||
		(task.assignee_ids ?? []).includes(userId) ||
		canManageWorkspace(teamRole, workspaceRole)
	);
}

export function canEditSubtask(
	subtask: { created_by_id?: string | null },
	task: Task,
	userId: string,
	teamRole: TeamRole | undefined,
	workspaceRole: WorkspaceRole | undefined
): boolean {
	return subtask.created_by_id === userId || canEditTask(task, userId, teamRole, workspaceRole);
}
```

- [ ] **Step 4: Run tests + typecheck**

Run: `npx vitest run src/lib/components/workos/lib/roles.test.ts`
Expected: PASS.
Run: `npm run check` (svelte-check) — expected: no new type errors from `roles.ts`.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/roles.ts src/lib/components/workos/lib/roles.test.ts
git commit -m "feat(workos): canEditTask/canEditSubtask predicates (cosmetic gate)"
```

---

# Phase 3 — Hardening (G7–G11)

## Task 6: Gate `GET /users` to team owners/admins (G7)

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (`list_users` [:148](../../../backend/open_webui/routers/workos.py:148))
- Modify: `backend/open_webui/test/workos/test_router_directory.py` (rewrite the two `/users` tests)
- Modify: `src/lib/components/workos/lib/api.ts` ([:114](../../../src/lib/components/workos/lib/api.ts:114)) and `src/lib/components/workos/views/ModalHost.svelte` ([:41](../../../src/lib/components/workos/views/ModalHost.svelte:41))

**Interfaces:**
- Produces: `GET /users?team_id=<id>` → `403` unless caller is a team owner/admin (or global admin); `422` if `team_id` is missing.
- Consumes: existing `require_team_role`, `list_all_users` (both already in the router).

- [ ] **Step 1: Rewrite the two existing `/users` tests (they encode the old contract)**

In `backend/open_webui/test/workos/test_router_directory.py`, replace `test_users_lists_all_app_users_not_just_team_members` ([:22-38](../../../backend/open_webui/test/workos/test_router_directory.py:22)) and `test_users_requires_workos_access` ([:41-49](../../../backend/open_webui/test/workos/test_router_directory.py:41)) with:

```python
@pytest.mark.asyncio
async def test_users_roster_returned_to_team_owner(monkeypatch):
    async def _fake_all_users():
        return [{'id': 'u1', 'name': 'Lara'}, {'id': 'u2', 'name': 'Yusuf'}, {'id': 'u3', 'name': 'Mona'}]

    monkeypatch.setattr(wr, 'list_all_users', _fake_all_users)
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        r = await c.get(f"/api/v1/workos/users?team_id={team['id']}")
        assert r.status_code == 200, r.text
        assert {row['id'] for row in r.json()} == {'u1', 'u2', 'u3'}


@pytest.mark.asyncio
async def test_users_denied_to_plain_member(monkeypatch):
    from open_webui.test.workos.test_router_teams import U2

    async def _fake_all_users():
        return []

    monkeypatch.setattr(wr, 'list_all_users', _fake_all_users)
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c:
        r = await c.get(f"/api/v1/workos/users?team_id={team['id']}")
        assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_users_requires_team_id(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        r = await c.get('/api/v1/workos/users')
        assert r.status_code == 422  # missing required query param


@pytest.mark.asyncio
async def test_users_requires_workos_access(monkeypatch):
    async def _fake_all_users():
        return []

    monkeypatch.setattr(wr, 'list_all_users', _fake_all_users)
    # team_id present so the handler body runs; the feature gate then rejects.
    async with _client(monkeypatch, user=U1, allow=False) as c:
        r = await c.get('/api/v1/workos/users?team_id=anything')
        assert r.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/open_webui/test/workos/test_router_directory.py -v`
Expected: the new owner/member/team_id tests FAIL (endpoint ignores `team_id` and has no role gate).

- [ ] **Step 3: Gate the endpoint**

Replace `list_users` ([:148-154](../../../backend/open_webui/routers/workos.py:148)) with:

```python
@router.get('/users')
async def list_users(
    request: Request, team_id: str,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    # Full app roster for the team "Add a user…" picker — gated to the people who
    # can actually add members (team owners/admins, or a global admin).
    await _require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner', 'admin'})
    return await list_all_users()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/open_webui/test/workos/test_router_directory.py -v`
Expected: all PASS.

- [ ] **Step 5: Update the frontend caller**

In `src/lib/components/workos/lib/api.ts` ([:114](../../../src/lib/components/workos/lib/api.ts:114)):

```ts
export const listAllUsers = (token: string, teamId: string) =>
	request<{ id: string; name: string }[]>(token, `/users?team_id=${encodeURIComponent(teamId)}`);
```

In `src/lib/components/workos/views/ModalHost.svelte` ([:41](../../../src/lib/components/workos/views/ModalHost.svelte:41)), pass the team id (`r.teamId` is already in scope in `reset`):

```ts
				api.listAllUsers(token(), r.teamId).catch(() => [])
```

- [ ] **Step 6: Typecheck + commit**

Run: `npm run check` (expected: no new errors). Then:

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_directory.py src/lib/components/workos/lib/api.ts src/lib/components/workos/views/ModalHost.svelte
git commit -m "fix(workos): restrict /users roster to team owners/admins (G7)"
```

---

## Task 7: Apply `default_workspace_visibility` (G8)

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (`WorkspaceForm` [:287](../../../backend/open_webui/routers/workos.py:287); `create_workspace` [:344](../../../backend/open_webui/routers/workos.py:344))
- Modify: `backend/open_webui/test/workos/test_router_teams.py` (`_make_app`/`_client` accept `rules=`)
- Test: `backend/open_webui/test/workos/test_router_hardening.py` (create)

**Interfaces:**
- Produces: new workspaces with no explicit `visibility` fall back to `WORKOS_RULES.default_workspace_visibility` (then `'team'`). `_make_app(user, rules=None)` / `_client(..., rules=None)`.

- [ ] **Step 1: Extend the test harness to allow custom rules**

In `backend/open_webui/test/workos/test_router_teams.py`, change `_make_app` ([:13](../../../backend/open_webui/test/workos/test_router_teams.py:13)) and `_client` ([:24](../../../backend/open_webui/test/workos/test_router_teams.py:24)):

```python
def _make_app(user, rules=None):
    app = FastAPI()
    app.state.config = SimpleNamespace(
        USER_PERMISSIONS={},
        WORKOS_RULES=rules or {'team_creation': 'all_users', 'default_workspace_visibility': 'team'},
    )
    app.include_router(wr.router, prefix='/api/v1/workos')
    app.dependency_overrides[get_verified_user] = lambda: user
    return app


def _client(monkeypatch, *, user, allow=True, rules=None):
    async def _hp(user_id, key, permissions, db=None):
        return allow
    monkeypatch.setattr(wr, 'has_permission', _hp)
    return httpx.AsyncClient(transport=ASGITransport(app=_make_app(user, rules)), base_url='http://test')
```

- [ ] **Step 2: Write the failing tests**

Create `backend/open_webui/test/workos/test_router_hardening.py`:

```python
import pytest

from open_webui.test.workos.test_router_teams import _client, U1


@pytest.mark.asyncio
async def test_workspace_defaults_to_configured_visibility(monkeypatch):
    rules = {'team_creation': 'all_users', 'default_workspace_visibility': 'restricted'}
    async with _client(monkeypatch, user=U1, rules=rules) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces", json={'name': 'Eng'})).json()
        assert ws['visibility'] == 'restricted'


@pytest.mark.asyncio
async def test_explicit_visibility_overrides_default(monkeypatch):
    rules = {'team_creation': 'all_users', 'default_workspace_visibility': 'restricted'}
    async with _client(monkeypatch, user=U1, rules=rules) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                           json={'name': 'Eng', 'visibility': 'team'})).json()
        assert ws['visibility'] == 'team'
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest backend/open_webui/test/workos/test_router_hardening.py -k visibility -v`
Expected: `test_workspace_defaults_to_configured_visibility` FAILS (gets `'team'`).

- [ ] **Step 4: Make the form optional and apply the rule**

In `WorkspaceForm` ([:287-290](../../../backend/open_webui/routers/workos.py:287)) change the default:

```python
class WorkspaceForm(BaseModel):
    name: str
    icon: Optional[str] = None
    visibility: Optional[str] = None
```

In `create_workspace` ([:349-353](../../../backend/open_webui/routers/workos.py:349)) replace the validation + insert lead-in:

```python
    await require_team_role(user, team_id, db, {'owner', 'admin'})
    rules = request.app.state.config.WORKOS_RULES or {}
    visibility = form.visibility or rules.get('default_workspace_visibility') or 'team'
    if visibility not in {'team', 'restricted'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid visibility.')
    ws = await Workspaces.insert(team_id, form.name, form.icon, visibility, user.id, db=db)
    if visibility == 'restricted':
        await WorkspaceMembers.add(ws.id, user.id, 'admin', db=db)
```

- [ ] **Step 5: Run tests + regression guard**

Run: `pytest backend/open_webui/test/workos/test_router_hardening.py -k visibility -v` (expect PASS).
Run: `pytest backend/open_webui/test/workos -q` (expect all green; `_stream` posts explicit `'team'`, unaffected).

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_teams.py backend/open_webui/test/workos/test_router_hardening.py
git commit -m "fix(workos): honor default_workspace_visibility rule (G8)"
```

---

## Task 8: Last-owner guard (G9)

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (`_is_last_owner`; `update_member` [:255](../../../backend/open_webui/routers/workos.py:255); `remove_member` [:271](../../../backend/open_webui/routers/workos.py:271))
- Test: `backend/open_webui/test/workos/test_router_hardening.py` (append)

**Interfaces:**
- Produces: `async _is_last_owner(team_id, user_id, db) -> bool`.
- Consumes: `TeamMembers.list_for_team` (returns rows with `.user_id`, `.role`).

- [ ] **Step 1: Write the failing tests**

Append to `backend/open_webui/test/workos/test_router_hardening.py`:

```python
@pytest.mark.asyncio
async def test_cannot_remove_last_owner(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        r = await c.delete(f"/api/v1/workos/teams/{team['id']}/members/u1")
        assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_can_remove_owner_when_another_owner_exists(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'owner'})
        r = await c.delete(f"/api/v1/workos/teams/{team['id']}/members/u1")
        assert r.json()['removed'] is True


@pytest.mark.asyncio
async def test_cannot_demote_last_owner(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        r = await c.patch(f"/api/v1/workos/teams/{team['id']}/members/u1", json={'role': 'admin'})
        assert r.status_code == 400, r.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/open_webui/test/workos/test_router_hardening.py -k owner -v`
Expected: `test_cannot_remove_last_owner` and `test_cannot_demote_last_owner` FAIL.

- [ ] **Step 3: Add `_is_last_owner` and apply both guards**

Add the helper just above `update_member` ([:255](../../../backend/open_webui/routers/workos.py:255)):

```python
async def _is_last_owner(team_id: str, user_id: str, db: AsyncSession) -> bool:
    members = await TeamMembers.list_for_team(team_id, db=db)
    owners = [m for m in members if m.role == 'owner']
    return len(owners) == 1 and owners[0].user_id == user_id
```

In `update_member`, after the `if form.role not in TEAM_ROLES` check ([:263-264](../../../backend/open_webui/routers/workos.py:263)):

```python
    if form.role != 'owner' and await _is_last_owner(team_id, user_id, db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Cannot demote the last team owner.')
```

In `remove_member`, after the `require_team_role(...)` line ([:277](../../../backend/open_webui/routers/workos.py:277)):

```python
    if await _is_last_owner(team_id, user_id, db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Cannot remove the last team owner.')
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/open_webui/test/workos/test_router_hardening.py -k owner -v`
Expected: all three PASS.

- [ ] **Step 5: Regression guard + commit**

Run: `pytest backend/open_webui/test/workos -q` (expect green). Then:

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_hardening.py
git commit -m "fix(workos): block removing/demoting the last team owner (G9)"
```

---

## Task 9: Clamp notification `limit` (G10)

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (`list_notifications` [:1064](../../../backend/open_webui/routers/workos.py:1064))
- Test: `backend/open_webui/test/workos/test_router_hardening.py` (append)

**Interfaces:**
- Produces: `GET /notifications` clamps `limit` to `[1, 200]` before the DAO call.

- [ ] **Step 1: Write the failing test**

Append to `backend/open_webui/test/workos/test_router_hardening.py`:

```python
@pytest.mark.asyncio
async def test_notifications_limit_is_clamped(monkeypatch):
    from open_webui.models.workos import Notifications
    captured = {}

    async def _fake_list(user_id, *, unread_only=False, limit=50, before=None, db=None):
        captured['limit'] = limit
        return []

    monkeypatch.setattr(Notifications, 'list_for_user', _fake_list)
    async with _client(monkeypatch, user=U1) as c:
        await c.get('/api/v1/workos/notifications?limit=99999')
    assert captured['limit'] == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/open_webui/test/workos/test_router_hardening.py -k clamp -v`
Expected: FAIL (`captured['limit'] == 99999`).

- [ ] **Step 3: Clamp the value**

In `list_notifications` ([:1069-1070](../../../backend/open_webui/routers/workos.py:1069)), insert before the return:

```python
    await _require_workos(request, user, db)
    limit = max(1, min(limit, 200))
    return await Notifications.list_for_user(user.id, unread_only=unread_only, limit=limit, before=before, db=db)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/open_webui/test/workos/test_router_hardening.py -k clamp -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_hardening.py
git commit -m "fix(workos): clamp notifications limit to 200 (G10)"
```

---

## Task 10: Attachment MIME allowlist + comment ownership (G11)

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (`ATTACHMENT_MIME_ALLOW`; `upload_attachment` [:967](../../../backend/open_webui/routers/workos.py:967))
- Test: `backend/open_webui/test/workos/test_router_hardening.py` (append)

**Interfaces:**
- Produces: `upload_attachment` rejects (`400`) a disallowed `content_type` and a `comment_id` that doesn't belong to the task. The MIME check is placed **after** the size check (so the existing octet-stream oversize test still exercises the size branch).

- [ ] **Step 1: Write the failing tests**

Append to `backend/open_webui/test/workos/test_router_hardening.py`:

```python
import io

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import U2
from open_webui.test.workos.test_router_attachments import _FakeStorage, _task as _att_task


@pytest.mark.asyncio
async def test_attachment_rejects_disallowed_mime(monkeypatch):
    monkeypatch.setattr(wr, 'Storage', _FakeStorage)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _att_task(c)
        files = {'file': ('x.exe', io.BytesIO(b'MZ'), 'application/x-msdownload')}
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments", files=files)
        assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_attachment_allows_whitelisted_mime(monkeypatch):
    monkeypatch.setattr(wr, 'Storage', _FakeStorage)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _att_task(c)
        files = {'file': ('notes.txt', io.BytesIO(b'hi'), 'text/plain')}
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments", files=files)
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_attachment_rejects_foreign_comment_id(monkeypatch):
    monkeypatch.setattr(wr, 'Storage', _FakeStorage)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _att_task(c)
        files = {'file': ('notes.txt', io.BytesIO(b'hi'), 'text/plain')}
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments?comment_id=nope", files=files)
        assert r.status_code == 400, r.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/open_webui/test/workos/test_router_hardening.py -k attachment -v`
Expected: the "rejects" tests FAIL (currently 200).

- [ ] **Step 3: Add the allowlist constant**

In `backend/open_webui/routers/workos.py`, just above `_max_attachment_bytes` ([:961](../../../backend/open_webui/routers/workos.py:961)):

```python
ATTACHMENT_MIME_ALLOW = {
    'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/svg+xml',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/plain', 'text/csv', 'text/markdown', 'application/json', 'application/zip',
}
```

- [ ] **Step 4: Enforce both checks (after the size check)**

In `upload_attachment`, immediately after the oversize check ([:976-977](../../../backend/open_webui/routers/workos.py:976)) and before the `import io as _io` line:

```python
    if file.content_type not in ATTACHMENT_MIME_ALLOW:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported file type.')
    if comment_id is not None:
        com = await Comments.get_by_id(comment_id, db=db)
        if not com or com.task_id != task_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid comment for this task.')
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest backend/open_webui/test/workos/test_router_hardening.py -k attachment -v`
Expected: all three PASS.

- [ ] **Step 6: Regression guard (existing attachment suite)**

Run: `pytest backend/open_webui/test/workos/test_router_attachments.py -v`
Expected: all PASS — every existing upload uses `text/plain` except the oversize test (`application/octet-stream`), which still hits the size branch first (cap monkeypatched to 0).

- [ ] **Step 7: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_hardening.py
git commit -m "fix(workos): attachment MIME allowlist + comment ownership check (G11)"
```

---

# Phase 4 — Docs

## Task 11: Update the access-control reference doc

**Files:**
- Modify: `docs/superpowers/specs/2026-06-26-workos-access-control.md`

**Interfaces:** none (documentation only). This satisfies the standing rule to keep the reference in sync.

- [ ] **Step 1: Mark §8 gaps closed**

In `docs/superpowers/specs/2026-06-26-workos-access-control.md` §8, prefix each of G1–G11 with a ✅ and a one-line "Closed (2026-06-27, commit …)" note referencing the fix. Keep the original description for history.

- [ ] **Step 2: Refresh the gate tables**

Update the §4 tables and §3 helper list to reflect the new reality:
- `PATCH /tasks/{id}` now also `require_task_writable` (no longer "ONLY visibility").
- `PATCH`/`DELETE /subtasks/{id}` now also `require_subtask_writable`.
- `GET /users` now requires `team_id` + team owner/admin.
- §5: `notify()` now filters recipients by `can_see_workstream`.
- §7: `default_workspace_visibility` is now **consumed** by `create_workspace`.
- Add the new helpers (`_recipient_is_admin`, `_validate_assignees`, `_is_workspace_manager`, `require_task_writable`, `require_subtask_writable`, `_is_last_owner`, `ATTACHMENT_MIME_ALLOW`).

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-06-26-workos-access-control.md
git commit -m "docs(workos): mark access-control gaps G1-G11 closed"
```

---

## Deferred / out of scope (stated, not silently dropped)

- **TaskDetail.svelte visual wiring of `canEditTask`/`canEditSubtask`.** The predicates ship and are tested (Task 5), but gating the ~6 `editing*` affordances + subtask controls in `TaskDetail.svelte` is deferred cosmetic polish. The backend (Tasks 3–4) fully enforces the policy, so this is non-load-bearing. Pick it up as a follow-up if you want the affordances hidden for non-editors.
- **Socket eviction on membership revocation** and the **§5 workspace/workstream metadata-to-team-room mismatch** — known residuals, not part of the G1–G11 set.
- **G11 allowlist tuning** — the starting set is broad; extend it (or move it to `WORKOS_RULES`) if real uploads need types not listed.

---

## Self-Review

**Spec coverage:** G1 → Task 2; G2 → Task 3; G3+G4 → Task 1; G5+G6 → Task 4; frontend predicates → Task 5; G7 → Task 6; G8 → Task 7; G9 → Task 8; G10 → Task 9; G11 → Task 10; reference-doc update → Task 11. All 11 gaps + the cross-cutting doc step are covered.

**Type/name consistency:** `_recipient_is_admin` (Tasks 1–2), `_is_workspace_manager` (Tasks 3–4), `require_task_writable(user, task, stream, db)` (Task 3), `require_subtask_writable(user, subtask, task, stream, db)` (Task 4), `_is_last_owner(team_id, user_id, db)` (Task 8), `canEditTask`/`canEditSubtask` (Task 5) — names are used identically wherever referenced.

**Ripples handled:** `test_router_multi_assignee.py` membership seeding (Task 2 step 5); `test_router_directory.py` `/users` contract rewrite (Task 6 step 1); `_make_app`/`_client` `rules=` extension (Task 7 step 1); G11 MIME check ordered after the size check to preserve the octet-stream oversize test (Task 10 step 4).
