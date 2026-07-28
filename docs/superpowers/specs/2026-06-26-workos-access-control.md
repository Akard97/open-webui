<!--
  WorkOS — Access Control & Visibility: engineering reference / source of truth.
  Generated 2026-06-26 on branch `osool` via a multi-agent audit (model layer, router
  endpoints + gate helpers, realtime/socket, frontend, config, tests) with adversarial
  verification of every reported gap. Line citations were spot-checked against source.
  KEEP IN SYNC whenever access/visibility logic changes (can_see_*, require_*_visible,
  notify(), socket workos:subscribe, WORKOS_RULES).

  2026-07-02: all access predicates + require_* gates were consolidated into
  backend/open_webui/utils/workos_access.py (the policy module — single source of
  truth). §2/§3 cite the new locations; router line cites in §4 predate the
  consolidation and have shifted up by ~120 lines (helper defs removed), but the
  gate-per-endpoint mapping is unchanged.

  2026-07-02 (later): Access console shipped — a dedicated frontend view for team
  owners/admins (and app-admins) to manage membership, roles, and workspace
  visibility. One new read endpoint (GET /access/overview, §4); all mutations
  reuse the existing gated endpoints. §6 updated (new view + predicate; the
  "visibility is create-only in the UI" bullet is now false).

  2026-07-02 (creator rule): can_see_workspace grants the workspace CREATOR
  (created_by_id) visibility into their own restricted workspace even without a
  member row, provided they still pass the team gate. Ripples: restricted nav
  fan-out includes the creator (_with_creator), remove_workspace_member never
  evicts the creator, and the flip-eviction predicate is creator-safe
  automatically. §2/§5 updated.

  2026-07-02 (later still): Access console page REMOVED (frontend only) — replaced by
  sidebar-integrated access management: kebab/right-click menus on workspace rows and
  the team card opening TeamSettingsDialog / WorkspaceSettingsDialog
  (chrome/access/*). GET /access/overview endpoint + tests kept (currently no
  frontend caller). §6 updated.

  2026-07-15: task.flag.attachment_required capability added (app-admin → creator;
  assignees/managers may edit tasks but not this flag). PATCH /tasks/{id}
  additionally blocks status→done with 400 ATTACHMENT_REQUIRED when the flag is
  set and the task has zero attachment rows. Tasks now require ≥1 assignee at
  create, and a patch may not clear assignees to [].

  2026-07-20: URL deep linking shipped (query-param sync, urlSync.ts). §6 gains a
  bullet; no access logic changed.

  2026-07-28: subtasks gained assignee_ids (JSON list) with a subset invariant
  against the parent task's list. POST /tasks/{id}/subtasks and PATCH
  /subtasks/{id} accept assignee_ids (validated via validate_assignees);
  assigning someone NOT already on the parent requires task.write on the parent
  (403 'Only task editors can add new people to the task.') — without this
  gate, any task-visible user could self-assign via a subtask and thereby gain
  task.write. Parent-side removal cascades off all subtasks (PATCH /tasks).
  New notification type 'subtask_assigned' shares the 'assigned' rules toggle
  and is visibility-filtered by notify() like every other type. subtask.write
  chain unchanged (subset invariant ⇒ subtask assignee is always a parent
  assignee). Assignment still confers no visibility.

  2026-07-28 (same day, race hardening after adversarial review): the subset
  invariant is now enforced transactionally, not just at the endpoint layer.
  (1) Auto-add uses Tasks.merge_assignees — the union is computed from the
  parent row re-read (FOR UPDATE where supported) inside the write transaction,
  never from the request's snapshot, so a concurrent assignee REMOVAL (an
  access revocation, since parent assignment grants task.write) can no longer
  be silently undone by a racing subtask write. (2) Parent-assignee removal and
  the subtask strip commit atomically via Tasks.update_with_cascade — the
  invariant can never half-commit; realtime emits fire only after commit.
  (3) Subtasks.insert/update_fields intersect assignee_ids against the parent
  read in the same transaction (Subtasks._parent_subset), so whichever side of
  a race commits second still satisfies the invariant. No capability or
  visibility semantics changed — only the concurrency guarantees.

  2026-07-28 (round 3, after a second adversarial review): SQLite — the
  default backend — has no row locks (with_for_update() is a no-op there and
  the legacy pysqlite transaction mode doesn't even open a transaction for the
  SELECT), so round 2's in-transaction reads were not actually serialized on
  SQLite. All assignee-invariant writers (Tasks.merge_assignees,
  Tasks.update_with_cascade, Subtasks.insert, Subtasks.update_fields assignee
  path) now additionally serialize on a process-local per-task asyncio lock
  (models/workos.py _task_write_lock). On Postgres the retained
  with_for_update() row locks protect across processes; on SQLite the lock is
  the guarantee and the supported topology is a single app process (locks are
  never evicted — eviction races would break mutual exclusion). Client side,
  editSubtask renders pending rows as confirmed-server-baseline ⊕ pending
  overlays: failed edits drop their overlay (no phantom optimistic state) and
  realtime subtask.updated payloads rebase under pending edits instead of
  clobbering them.

  2026-07-28 (threaded comments): comments gained `parent_id` (reply
  threading) and a tombstone fork on delete — comments with replies are
  tombstoned (body/mentions cleared, `deleted_at` set, reactions purged)
  instead of hard-deleted so children survive; childless comments still
  hard-delete. Replying to a missing/cross-task/tombstoned parent is
  rejected (404/400). A new `POST /comments/{id}/reactions` endpoint
  (`require_workos` + `require_task_visible`, fixed emoji allowlist, no
  capability gate) lets any task-visible member toggle a reaction; realtime
  `workos:comment.reaction` joins the existing `comment.*` events in the
  workstream room, and tombstoning emits `workos:comment.updated` (not
  `comment.deleted`). Notification fan-out gained a `replied` type (own
  `WORKOS_RULES.notifications` toggle key, defaults enabled like all types)
  ranked between `mentioned` and `commented` — the parent comment's author is
  notified once as `replied` when not already mentioned, never duplicated as
  `commented`. Comment attachments (`POST /tasks/{id}/attachments` with
  `comment_id`) must now be images (`content_type` starts with `image/`);
  task-level uploads are unaffected.
-->

# WorkOS — Access Control & Visibility (Reference)

> Source of truth for how WorkOS (the task-management tool) decides who can see and do what. All line citations are against the `osool` branch as analyzed. Two layers exist throughout: a **feature gate** (can you use the tool at all) and a **containment/visibility model** (which slice of the Team → Workspace → Workstream → Task tree you can see and mutate).

---

## 1. Overview

WorkOS data is a strict **single-parent containment tree**:

```
Team ──< Workspace ──< Workstream ──< Task ──< Subtask
                                        └──< Comment, Attachment, Activity
```

Every node has exactly one parent. Access flows **down** the tree from a gate that bottoms out at **team membership**, with one per-workspace switch (`visibility`) that can narrow a workspace below its team.

There are **two distinct user→thing relationships, and they must not be conflated**:

| Relationship | Stored as | Grants access? |
|---|---|---|
| **Membership / access** | `WorkosTeamMember` rows, `WorkosWorkspaceMember` rows, plus the per-workspace `visibility` flag | **YES.** This is what makes a node visible (one exception: the workspace **creator** keeps visibility into their own restricted workspace without a member row — §2 creator rule, 2026-07-02). |
| **Task assignment** | `WorkosTask.assignee_ids` (a JSON list on the task itself, [workos.py:470](backend/open_webui/models/workos.py:470)) | **NO.** Being an assignee is *not* an access grant. An assignee who is not also a member who can see the workstream **cannot open the task** ([require_task_visible](backend/open_webui/routers/workos.py:581) never consults `assignee_ids`). |

This split is the root of several gaps in §8: the assignee picker and notification fan-out treat assignment as if it implied access, but the visibility gate does not — so a task can be assigned to (and a notification pushed to) someone who then gets a 404 trying to open it.

Subtasks carry their own `assignee_ids` (JSON list on `workos_subtask`), constrained to a **subset of the parent task's list** (auto-add on grow — gated by `task.write` — and cascade on parent shrink). Like task assignment, subtask assignment grants **no visibility**.

Key structural facts:
- **Workstreams have no visibility column** — they inherit the workspace gate 1:1 ([WorkosWorkstream](backend/open_webui/models/workos.py:86)).
- **Tasks have no visibility column and no `can_see_task` helper** — task visibility is *derived* entirely from `can_see_workstream(task.workstream_id)` ([WorkosTask](backend/open_webui/models/workos.py:458)).
- **App-level admins (`user.role == 'admin'`) are super-users** across all teams/workspaces, including restricted ones. A *team* owner/admin role grants **no** bypass of a restricted-workspace gate — only the app-level flag does.

---

## 2. The core mechanism

All canonical visibility logic lives in the **policy module** [utils/workos_access.py](backend/open_webui/utils/workos_access.py) (since 2026-07-02): pure boolean predicates (`can_see_team` / `can_see_workspace` / `can_see_workstream`) plus their request-path twins, the `require_*` helpers (§3), which raise `404` instead of returning `False`. The router, `notify()`, and the socket `workos:subscribe` handler all import from this one module — there are no duplicate copies of the rule anymore (the former router-local `workspace_visible` and the inline bootstrap filter were folded into `can_see_workspace`).

### `WorkosWorkspace.visibility`
[workos.py:68](backend/open_webui/models/workos.py:68) — `Column(Text, default='team')`, comment `"team | restricted"`. The single per-workspace switch:
- `'team'` → visible to **every team member**.
- `'restricted'` → visible **only** to explicit `WorkosWorkspaceMember` rows (plus app-admins).

Default on raw insert is `'team'`; the DAO insert takes `visibility` as an explicit arg ([workos.py:286](backend/open_webui/models/workos.py:286)), so the create path always sets it.

### `can_see_team(user_id, is_admin, team_id)` — [workos_access.py:56](backend/open_webui/utils/workos_access.py:56)

| Branch | Meaning |
|---|---|
| `if is_admin: return Teams.get_by_id(team_id) is not None` | App-admin sees the team **iff it exists** — no membership row needed. |
| `return TeamMembers.get(team_id, user_id) is not None` | Non-admin sees the team **iff a membership row exists**, *any role* (owner/admin/member all qualify). |

Only **row existence** is tested — the three team roles are equivalent for *visibility*.

### `can_see_workspace(user_id, is_admin, workspace)` — [workos_access.py:62](backend/open_webui/utils/workos_access.py:62)

The canonical per-workspace rule (takes a resolved workspace row):

| Branch | Meaning |
|---|---|
| `if not can_see_team(...): return False` | **Outer wall:** must pass the team gate first. Short-circuits regardless of workspace visibility. Note this means an app-admin cannot see a workspace orphaned by a deleted team (pre-consolidation the router path allowed it; unified 2026-07-02 to the stricter semantic — unreachable via normal flows). |
| `if workspace.visibility == 'team' or is_admin: return True` | Team-visible workspace → any team member passes; **or** app-admin passes even when restricted. |
| `if workspace.created_by_id == user_id: return True` | **Creator rule (2026-07-02):** the workspace creator keeps visibility even when restricted with no member row (covers someone else flipping it after creation). Team gate still applies — a creator who left the team sees nothing. |
| `return WorkspaceMembers.get(workspace.id, user_id) is not None` | Reached **only** when `restricted` AND not admin AND not creator: need an explicit workspace-member row, *any workspace role*. |

### `can_see_workstream(user_id, is_admin, workstream_id)` — [workos_access.py:75](backend/open_webui/utils/workos_access.py:75)

Resolves the workstream (`False` if unknown/deleted), then its parent workspace (`False` if orphaned), then delegates to `can_see_workspace`. Workstreams have no visibility of their own.

**Task visibility = `can_see_workstream(task.workstream_id)`.** Collapsed: *team gate passes* AND (*workspace is `'team'`* OR *app-admin* OR *explicit restricted-workspace member*). Tasks cannot be made more or less visible than their workstream.

---

## 3. Membership & roles

### Roles (stored as free-text `Text` columns; only existence is tested for *visibility*, role value matters for *write/manage*)

| Scope | Table | Roles | Unique constraint |
|---|---|---|---|
| Team | `WorkosTeamMember` ([workos.py:50](backend/open_webui/models/workos.py:50)) | `owner` \| `admin` \| `member` (col [:57](backend/open_webui/models/workos.py:57)) | `(team_id, user_id)` ([:52](backend/open_webui/models/workos.py:52)) |
| Workspace | `WorkosWorkspaceMember` ([workos.py:75](backend/open_webui/models/workos.py:75)) | `admin` \| `member` (col [:82](backend/open_webui/models/workos.py:82)) | `(workspace_id, user_id)` ([:77](backend/open_webui/models/workos.py:77)) |

Role values are validated at the model layer (since 2026-07-02): `TEAM_ROLES` / `WORKSPACE_ROLES` are defined in [models/workos.py](backend/open_webui/models/workos.py) next to the tables, and the four DAO write methods (`TeamMembers.add`/`update_role`, `WorkspaceMembers.add`/`update_role`) raise `ValueError` on any other string. The router additionally 400s on invalid roles at the member endpoints (user-facing), importing the same constants via the policy module re-export.

### Role-resolution & gate helpers (policy module — [utils/workos_access.py](backend/open_webui/utils/workos_access.py))

All rows below live in the policy module since 2026-07-02 (formerly router-local; the leading underscores were dropped when they moved). `ATTACHMENT_MIME_ALLOW` is the one exception — it stays in the router (transport concern, not access policy).

| Helper | Location | Behavior |
|---|---|---|
| `require_workos` / `require_workos_admin` | [workos_access.py:39](backend/open_webui/utils/workos_access.py:39) | Feature gates (§7): `401 'WorkOS access required.'` / `403 'WorkOS admin required.'` unless global admin or `has_permission`. |
| `team_role(user, team_id)` | [workos_access.py:87](backend/open_webui/utils/workos_access.py:87) | Returns `'admin'` immediately for global admins (**no membership row required**); else the `TeamMembers.get(...).role` or `None`. `None` == not visible. |
| `require_team_visible` | [workos_access.py:115](backend/open_webui/utils/workos_access.py:115) | `404` if team missing OR `team_role is None`. Passers: global admins + any team member. |
| `require_team_role(..., allowed)` | [workos_access.py:122](backend/open_webui/utils/workos_access.py:122) | `require_team_visible` first; global admin early-returns; else `team_role ∈ allowed` else `403 'Insufficient role.'` Used with `{'owner','admin'}` / `{'owner'}`. |
| `can_see_workspace(user_id, is_admin, ws)` | [workos_access.py:62](backend/open_webui/utils/workos_access.py:62) | The canonical workspace predicate (§2). Replaces the former router `workspace_visible` and the inline bootstrap filter. |
| `require_workspace_visible` | [workos_access.py:131](backend/open_webui/utils/workos_access.py:131) | `404` if missing OR not `can_see_workspace`. |
| `require_workspace_manage` | [workos_access.py:138](backend/open_webui/utils/workos_access.py:138) | `require_workspace_visible` first (so a team owner/admin who is **not** a member of a *restricted* workspace is blocked at the `404` visibility step, never reaching manage). Then pass if `is_workspace_manager`; else `403`. |
| `require_workstream_visible` | [workos_access.py:145](backend/open_webui/utils/workos_access.py:145) | `404` if missing, then delegates to `require_workspace_visible`. Returns `(stream, ws)`. No own visibility flag. |
| `require_task_visible` | [workos_access.py:153](backend/open_webui/utils/workos_access.py:153) | `404` if missing, then `require_workstream_visible`. Returns `(task, stream)`. **No per-task ACL; assignees get no extra read access.** |
| `require_subtask_visible` | [workos_access.py:161](backend/open_webui/utils/workos_access.py:161) | `404` if missing, then `require_task_visible`. Returns `(subtask, task, stream)`. |
| `is_app_admin` (was `_recipient_is_admin`) | [workos_access.py:107](backend/open_webui/utils/workos_access.py:107) | bool predicate: `True` if recipient's `role == 'admin'`; used by `notify()` to let platform admins always receive notifications regardless of workstream visibility. |
| `validate_assignees` | [workos_access.py:203](backend/open_webui/utils/workos_access.py:203) | validates each id in `assignee_ids` via `can_see_workstream`; rejects the whole request if any id fails. Closes G1. |
| `is_workspace_manager` | [workos_access.py:94](backend/open_webui/utils/workos_access.py:94) | bool predicate: `True` if `team_role ∈ {'owner','admin'}` OR workspace-member `role == 'admin'`; used by write-gate helpers. |
| `require_task_writable` | [workos_access.py:172](backend/open_webui/utils/workos_access.py:172) | `403` unless caller is app-admin, creator, an assignee, or `is_workspace_manager`. Called after `require_task_visible`. Closes G2. |
| `require_subtask_writable` | [workos_access.py:186](backend/open_webui/utils/workos_access.py:186) | `403` unless caller is app-admin, subtask creator, task creator/assignee, or `is_workspace_manager`. Called after `require_subtask_visible`. Closes G5 + G6. |
| `is_last_owner` | [workos_access.py:101](backend/open_webui/utils/workos_access.py:101) | `True` if `user_id` is the sole owner-role member of `team_id`; used by `remove_member` guard. Closes G9. |
| `ATTACHMENT_MIME_ALLOW` | [workos.py](backend/open_webui/routers/workos.py) | Frozenset of permitted MIME types for uploaded attachments; upload rejected if `file.content_type` not in set. Closes G11. (Router, not policy module.) |

### Capability registry (2026-07-02)

Every resource-write rule is table-driven in the policy module — the former scattered per-endpoint if-chains are gone. `require_capability(cap, user, db, **ctx)` walks the ordered rules and raises `403` with the capability's pinned detail string; `require_team_capability` names the `require_team_role` allowed-sets.

`CAPABILITIES` (ordered rules → 403 detail):

| Capability | Rule order | Used by |
|---|---|---|
| `task.write` | app-admin → creator → assignee → workspace-manager | `require_task_writable` → `PATCH /tasks/{id}` |
| `task.delete` | team owner/admin (incl. app-admin via `team_role`) → creator | `DELETE /tasks/{id}` |
| `task.flag.attachment_required` | app-admin → creator | `PATCH /tasks/{id}` when the patch changes attachment_required |
| `subtask.write` | app-admin → subtask creator → task creator → assignee → workspace-manager | `require_subtask_writable` → subtask PATCH/DELETE |
| `comment.edit` | author **only** (deliberately NO app-admin bypass) | `PATCH /comments/{id}` |
| `comment.delete` | team owner/admin → author | `DELETE /comments/{id}` |
| `attachment.delete` | team owner/admin → uploader | `DELETE /attachments/{id}` |

`TEAM_CAPABILITIES`: `team.members.manage` {owner,admin}; `team.members.grant_privileged` {owner} (granting owner/admin); `labels.manage` {owner,admin}; `workspace.delete` {owner,admin}. Detail strings are pinned byte-for-byte by `test_policy_module.py` / `test_capability_matrix.py`.

All `require_*_visible` helpers return **`404` (not `403`)** when a row is missing *or* invisible, so non-members cannot distinguish "doesn't exist" from "you can't see it."

> **Note on admin omniscience:** because `team_role` returns `'admin'` for any global admin with no membership row, and `can_see_workstream`/`can_see_workspace` short-circuit on `is_admin`, restricted workspaces offer **no confidentiality from platform admins**. This is intentional super-user behavior; an audit reading only the membership tables will not reflect it.

---

## 4. Every backend element that USES access control

All routes are authenticated with `get_verified_user` and call `require_workos` (regular) or `require_workos_admin` (`/admin/*`) **first**. The table lists the *additional* gate(s) layered on top. Global admins (`user.role == 'admin'`) bypass every gate.

### Directory / bootstrap
| Route / Helper | Gate applied | Location |
|---|---|---|
| `GET /directory` | `require_workos`; result scoped to caller's team co-members (`Teams.list_for_user` → `TeamMembers.list_for_team`), admin sees all | [workos.py:136](backend/open_webui/routers/workos.py:136) |
| `GET /users` | `require_workos` + `team_id` query-param required + `require_team_role({'owner','admin'})` — returns team-scoped roster (id+name); non-owner/admin gets `403` (closes G7) | [workos.py:148](backend/open_webui/routers/workos.py:148) |
| `GET /bootstrap` | `require_workos`; teams scoped to user; **inline workspace visibility filter** (`visibility=='team'` OR admin OR `WorkspaceMembers.get`) at [:170](backend/open_webui/routers/workos.py:170) | [workos.py:160](backend/open_webui/routers/workos.py:160) |

### Teams
| Route / Helper | Gate applied | Location |
|---|---|---|
| `GET /teams` | `require_workos`; `Teams.list_for_user` (admin → `list_all`) | [workos.py:182](backend/open_webui/routers/workos.py:182) |
| `POST /teams` | `require_workos`; `WORKOS_RULES.team_creation=='admins_only'` → admin only ([:193–195](backend/open_webui/routers/workos.py:193)); creator becomes owner | [workos.py:188](backend/open_webui/routers/workos.py:188) |
| `GET /teams/{id}` | `require_workos` + `require_team_visible` | [workos.py:204](backend/open_webui/routers/workos.py:204) |
| `PATCH /teams/{id}` | `require_workos` + `require_team_role({'owner'})` | [workos.py:212](backend/open_webui/routers/workos.py:212) |
| `DELETE /teams/{id}` | `require_workos` + `require_team_role({'owner'})` | [workos.py:223](backend/open_webui/routers/workos.py:223) |
| `GET /teams/{id}/members` | `require_workos` + `require_team_visible` | [workos.py:232](backend/open_webui/routers/workos.py:232) |
| `POST /teams/{id}/members` | `require_workos` + `require_team_role({'owner','admin'})`; role validated; dup check | [workos.py:241](backend/open_webui/routers/workos.py:241) |
| `PATCH /teams/{id}/members/{uid}` | `require_workos` + `require_team_role({'owner'})` when granting owner/admin else `{'owner','admin'}` | [workos.py:255](backend/open_webui/routers/workos.py:255) |
| `DELETE /teams/{id}/members/{uid}` | `require_workos` + `require_team_role({'owner','admin'})`; rejects if `is_last_owner(team_id, uid)` (closes G9) | [workos.py:271](backend/open_webui/routers/workos.py:271) |

### Workspaces
| Route / Helper | Gate applied | Location |
|---|---|---|
| `GET /teams/{id}/workspaces` | `require_workos` + `require_team_visible`, then per-ws `can_see_workspace` filter | [workos.py:331](backend/open_webui/routers/workos.py:331) |
| `POST /teams/{id}/workspaces` | `require_workos` + `require_team_role({'owner','admin'})`; visibility validated; restricted → creator added as workspace admin | [workos.py:344](backend/open_webui/routers/workos.py:344) |
| `GET /workspaces/{id}` | `require_workos` + `require_workspace_visible` | [workos.py:360](backend/open_webui/routers/workos.py:360) |
| `PATCH /workspaces/{id}` | `require_workos` + `require_workspace_manage`; visibility validated | [workos.py:368](backend/open_webui/routers/workos.py:368) |
| `DELETE /workspaces/{id}` | `require_workos` + `require_workspace_visible` + `require_team_role({'owner','admin'})` | [workos.py:383](backend/open_webui/routers/workos.py:383) |
| `GET /workspaces/{id}/members` | `require_workos` + `require_workspace_visible` | [workos.py:398](backend/open_webui/routers/workos.py:398) |
| `POST /workspaces/{id}/members` | `require_workos` + `require_workspace_manage`; role validated; dup check (target not validated as team member) | [workos.py:407](backend/open_webui/routers/workos.py:407) |
| `PATCH /workspaces/{id}/members/{uid}` | `require_workos` + `require_workspace_manage`; role validated | [workos.py:421](backend/open_webui/routers/workos.py:421) |
| `DELETE /workspaces/{id}/members/{uid}` | `require_workos` + `require_workspace_manage` | [workos.py:436](backend/open_webui/routers/workos.py:436) |

### Workstreams
| Route / Helper | Gate applied | Location |
|---|---|---|
| `GET /workspaces/{id}/workstreams` | `require_workos` + `require_workspace_visible` | [workos.py:474](backend/open_webui/routers/workos.py:474) |
| `POST /workspaces/{id}/workstreams` | `require_workos` + `require_workspace_manage` | [workos.py:483](backend/open_webui/routers/workos.py:483) |
| `PATCH /workstreams/{id}` | `require_workos` + `require_workstream_visible` + `require_workspace_manage` | [workos.py:496](backend/open_webui/routers/workos.py:496) |
| `DELETE /workstreams/{id}` | `require_workos` + `require_workstream_visible` + `require_workspace_manage` | [workos.py:510](backend/open_webui/routers/workos.py:510) |

### Tasks
| Route / Helper | Gate applied | Location |
|---|---|---|
| `GET /workstreams/{id}/tasks` | `require_workos` + `require_workstream_visible` | [workos.py:605](backend/open_webui/routers/workos.py:605) |
| `POST /workstreams/{id}/tasks` | `require_workos` + `require_workstream_visible` + `require_team_visible`; field validation; `assignee_ids` validated via `validate_assignees` (closes G1); assignee_ids must be non-empty (400) | [workos.py:614](backend/open_webui/routers/workos.py:614) |
| `GET /tasks/{id}` | `require_workos` + `require_task_visible` | [workos.py:634](backend/open_webui/routers/workos.py:634) |
| `GET /me/tasks` | `require_workos`; intrinsically user-scoped; returns tasks where caller is creator OR in `assignee_ids`, each filtered through `can_see_workstream` (assignment/authorship confer no access — visibility still enforced); admin scoped to own created/assigned across all teams | [workos.py:657](backend/open_webui/routers/workos.py:657) |
| `PATCH /tasks/{id}` | `require_workos` + `require_task_visible` + `require_task_writable`; `assignee_ids` validated via `validate_assignees` (closes G1 + G2); attachment_required changes gated by require_capability('task.flag.attachment_required'); status→done blocked (400 ATTACHMENT_REQUIRED) when flagged with no attachments | [workos.py:643](backend/open_webui/routers/workos.py:643) |
| `DELETE /tasks/{id}` | `require_workos` + `require_task_visible` + `require_capability('task.delete')` — creator or team owner/admin (`403` else) | [workos.py:677](backend/open_webui/routers/workos.py:677) |

### Labels
| Route / Helper | Gate applied | Location |
|---|---|---|
| `GET /teams/{id}/labels` | `require_workos` + `require_team_visible` | [workos.py:697](backend/open_webui/routers/workos.py:697) |
| `POST /teams/{id}/labels` | `require_workos` + `require_team_visible` **only** (by design: any team member may create tags); no value validation | [workos.py:706](backend/open_webui/routers/workos.py:706) |
| `PATCH /labels/{id}` | `require_workos`; fetch label (`404`), then `require_team_role({'owner','admin'})` on `label.team_id` | [workos.py:717](backend/open_webui/routers/workos.py:717) |
| `DELETE /labels/{id}` | `require_workos`; fetch label (`404`), then `require_team_role({'owner','admin'})` | [workos.py:730](backend/open_webui/routers/workos.py:730) |

### Comments / activity
| Route / Helper | Gate applied | Location |
|---|---|---|
| `GET /tasks/{id}/comments` | `require_workos` + `require_task_visible` | [workos.py:1006](backend/open_webui/routers/workos.py:1006) |
| `POST /tasks/{id}/comments` | `require_workos` + `require_task_visible`; `parent_id` (if given) must resolve to a comment on the same task and not be tombstoned (`404`/`400` else); mentions re-checked via `can_see_workstream` before notifying (leak-safe); notification fan-out is precedence-ordered **mentioned > replied > commented** — one notification per recipient | [workos.py:1022](backend/open_webui/routers/workos.py:1022) |
| `PATCH /comments/{id}` | `require_workos`; fetch (`404`); `require_task_visible`; `require_capability('comment.edit')` — **author-only, no admin bypass** (`403` else); new mentions re-checked | [workos.py:1068](backend/open_webui/routers/workos.py:1068) |
| `DELETE /comments/{id}` | `require_workos`; fetch (`404`); `require_task_visible`; `require_capability('comment.delete')` — **author OR team owner/admin** (`403` else); forks on children: comments with replies are **tombstoned** (body/mentions cleared, `deleted_at` set, reactions purged, children survive) instead of hard-deleted; childless comments hard-delete as before | [workos.py:1098](backend/open_webui/routers/workos.py:1098) |
| `POST /comments/{id}/reactions` | `require_workos`; fetch (`404`); `require_task_visible`; emoji checked against the `REACTION_EMOJI` allowlist (`400` else); tombstoned-comment reactions rejected (`400`); **no `require_capability` entry** — any task-visible member may react; toggles the caller's own reaction only, notifies nobody | [workos.py:1130](backend/open_webui/routers/workos.py:1130) |
| `GET /tasks/{id}/activity` | `require_workos` + `require_task_visible` | [workos.py:1156](backend/open_webui/routers/workos.py:1156) |
| `GET /workstreams/{id}/activity` | `require_workos` + `require_workstream_visible` — workstream-scoped activity list (items joined w/ task key/title) + tz-aware daily histogram; `limit`≤100, `days`≤31 clamped | [workos.py:1046](backend/open_webui/routers/workos.py:1046) |

### Attachments
| Route / Helper | Gate applied | Location |
|---|---|---|
| `POST /tasks/{id}/attachments` | `require_workos` + `require_task_visible`; size limit; MIME checked against `ATTACHMENT_MIME_ALLOW`; `comment_id` validated against `task_id` before insert (closes G11); when `comment_id` is set, `content_type` must additionally start with `image/` (`400` else) — task-level uploads (no `comment_id`) are unaffected | [workos.py:1218](backend/open_webui/routers/workos.py:1218) |
| `GET /tasks/{id}/attachments` | `require_workos` + `require_task_visible` | [workos.py:998](backend/open_webui/routers/workos.py:998) |
| `GET /workstreams/{id}/attachments` | `require_workos` + `require_workstream_visible` — workstream-wide listing (rows joined w/ task key/title/status), read-only, cap 1000 | [workos.py:1148](backend/open_webui/routers/workos.py:1148) `list_workstream_attachments` |
| `GET /attachments/{id}/content` | `require_workos`; fetch (`404`); `require_task_visible` on `att.task_id` — visibility-gated, OK | [workos.py:1007](backend/open_webui/routers/workos.py:1007) |
| `DELETE /attachments/{id}` | `require_workos`; fetch (`404`); `require_task_visible`; `require_capability('attachment.delete')` — **uploader OR team owner/admin** (`403` else) | [workos.py:1031](backend/open_webui/routers/workos.py:1031) |

### Subtasks
| Route / Helper | Gate applied | Location |
|---|---|---|
| `GET /tasks/{id}/subtasks` | `require_workos` + `require_task_visible` | [workos.py:1101](backend/open_webui/routers/workos.py:1101) |
| `POST /tasks/{id}/subtasks` | `require_workos` + `require_task_visible`; title required; `assignee_ids` validated via `validate_assignees`, defaults to parent's first assignee; ids not on the parent additionally require `require_task_writable` (auto-add) | [workos.py:1110](backend/open_webui/routers/workos.py:1110) |
| `PATCH /subtasks/{id}` | `require_workos` + `require_subtask_visible` + `require_subtask_writable` (closes G5); `assignee_ids` edits validated via `validate_assignees`; expanding the parent list additionally requires `require_task_writable` | [workos.py:1128](backend/open_webui/routers/workos.py:1128) |
| `DELETE /subtasks/{id}` | `require_workos` + `require_subtask_visible` + `require_subtask_writable` (closes G6) | [workos.py:1155](backend/open_webui/routers/workos.py:1155) |

### Notifications
| Route / Helper | Gate applied | Location |
|---|---|---|
| `GET /notifications` | `require_workos`; intrinsically scoped to `user.id`; `limit` clamped to ≤ 200 (closes G10); `archived` query param filters archived vs inbox rows | [workos.py:1064](backend/open_webui/routers/workos.py:1064) |
| `POST /notifications/read` | `require_workos`; `Notifications.mark_read` passed `user.id` | [workos.py:1073](backend/open_webui/routers/workos.py:1073) |
| `GET /notifications/counts` | `require_workos`; intrinsically scoped to `user.id`; unread + non-archived per-type counts | [workos.py](backend/open_webui/routers/workos.py) `notification_counts` |
| `POST /notifications/archive` | `require_workos`; `Notifications.set_archived` passed `user.id` (owner-scoped; archive implies read) | [workos.py](backend/open_webui/routers/workos.py) `archive_notifications` |

### Access console
| Route / Helper | Gate applied | Location |
|---|---|---|
| `GET /access/overview` | `require_workos` only; result intrinsically scoped — one row per team where the caller's `team_role ∈ {'owner','admin'}` (app-admin: all teams incl. archived), each row's `workspaces` filtered through `can_see_workspace` so restricted workspaces the caller is not a member of are **omitted** (§9 decision holds — no owner/admin bypass); non-managers get `[]` (no error, no leak). **Note:** endpoint currently has **no frontend caller** (kept deliberately). | [workos.py](backend/open_webui/routers/workos.py) `access_overview` |

### Admin
| Route / Helper | Gate applied | Location |
|---|---|---|
| `GET /admin/teams` | `require_workos_admin`; lists all teams + owner ids + counts | [workos.py:755](backend/open_webui/routers/workos.py:755) |
| `GET /admin/settings` | `require_workos_admin`; returns `WORKOS_RULES` | [workos.py:771](backend/open_webui/routers/workos.py:771) |
| `PATCH /admin/settings` | `require_workos_admin`; validates `team_creation`/`default_workspace_visibility`/`max_attachment_mb`; merges into `app.state.config.WORKOS_RULES` | [workos.py:779](backend/open_webui/routers/workos.py:779) |

### Foundation gates / model helpers
| Helper | Behavior | Location |
|---|---|---|
| `require_workos` | `401` unless `role=='admin'` or `has_permission('features.workos')` | [workos_access.py:39](backend/open_webui/utils/workos_access.py:39) |
| `require_workos_admin` | `403` unless `role=='admin'` or `has_permission('features.workos_admin')` | [workos_access.py:46](backend/open_webui/utils/workos_access.py:46) |
| `has_permission` | dotted-key resolver over group perms → default perms | [access_control/__init__.py](backend/open_webui/utils/access_control/__init__.py) |
| `can_see_team` / `can_see_workspace` / `can_see_workstream` | non-raising bool predicates used outside the request path (notifications/mentions/socket join) | [workos_access.py:56](backend/open_webui/utils/workos_access.py:56) / [:62](backend/open_webui/utils/workos_access.py:62) / [:75](backend/open_webui/utils/workos_access.py:75) |

---

## 5. Realtime & notifications scoping

Two independent push channels with **different** gating postures.

### Channel A — Socket.IO shared rooms (correctly gated at JOIN)
Three room namespaces: `workos:team:{team_id}`, `workos:workstream:{workstream_id}`, and the platform per-user room `user:{id}`.

- **The only join path** is the `workos:subscribe` handler ([socket/main.py:477](backend/open_webui/socket/main.py:477)). Since 2026-07-02 it trusts the **connection's established session identity** (`SESSION_POOL[sid]`, set at connect/user-join) — a token in the event payload is ignored, and no session means no join (fail closed). It calls `enter_room` **only after** `can_see_team` / `can_see_workstream` pass. There is no auto-join anywhere.
- Every workstream-scoped emit targets `workos:workstream:{task.workstream_id}` (via `_emit_task_room`, [workos.py:999](backend/open_webui/routers/workos.py:999)); `emit_event` ([workos.py:26](backend/open_webui/routers/workos.py:26)) does no access check by design — security is at the join. Comment-related events in this room: `workos:comment.created`, `workos:comment.updated`, `workos:comment.deleted`, `workos:comment.reaction` (reaction toggle). Tombstoning a comment (has children) emits `workos:comment.updated` with the cleared body, not `workos:comment.deleted` — the row survives for its children.
- **Conclusion (verified):** a user who fails `can_see_workstream` **cannot receive** task/comment/activity/subtask/attachment realtime events. This claim was checked and is accurate, *not* overstated.

**Realtime caveats — all three CLOSED (2026-07-02):**
- **Eviction on revocation — FIXED.** `remove_member` evicts the removed user's live sockets from the team room and every workstream room under the team; `remove_workspace_member` evicts from the workspace's workstream rooms when (and only when) the workspace is `restricted` (removal from a team-visible workspace revokes nothing, and app-admin targets and the **workspace creator** are never evicted — they retain access). Implemented via `workos_leave_rooms` in [socket/main.py](backend/open_webui/socket/main.py) behind the best-effort `evict_user` wrapper in the router. *Known limit:* room membership is per-worker (`sio.manager.get_participants`), so eviction is best-effort in scale-out — same posture as `disconnect_user_sessions`.
- **Token-in-payload — FIXED.** `workos:subscribe` now authorizes from `SESSION_POOL[sid]` (connection identity); payload tokens are ignored, absent session fails closed. The client no longer sends a token in the subscribe payload ([store.ts emitSub](src/lib/components/workos/lib/store.ts)).
- **Structural scoping mismatch — FIXED.** Workspace/workstream nav events are now **visibility-routed** by `_emit_nav_event` in the router: `visibility=='team'` → team-wide room as before; `restricted` → each workspace member's (plus the creator's, via `_with_creator`) `user:{id}` room. Plain team members no longer receive restricted names/metadata.
  - **Visibility-flip protocol** (`_emit_workspace_updated`): on `team→restricted`, the team room gets a `workspace.deleted`-shaped event FIRST (clients drop the subtree), then members get the full `workspace.updated` + one `workstream.created` per child stream over their user rooms (subtree rebuild), then sockets that can no longer see each child workstream are evicted from its room (`workos_evict_room_non_members`). On `restricted→team`, the team room gets the full `workspace.updated` + `workstream.created` per child stream. Emission order is load-bearing and pinned by tests (`test_router_restricted_emits.py`, `store.test.ts`).
  - Frontend consequence: the old §6 client-side guard that refused restricted payloads from nav events was removed (the server now only delivers restricted payloads to authorized sockets, and the guard broke the flip rebuild); the workstream parent-visibility check remains.

### Channel B — Per-user notification fan-out (now visibility-gated — closes G3+G4)
**Before the G3+G4 fix**, `notify()` ([workos.py:817](backend/open_webui/routers/workos.py:817)) built `targets = {r for r in recipients if r and r != actor.id}`, inserted a `Notification` row per target, and called `emit_users('workos:notification.created', …)` to that user's `user:{id}` room ([:838](backend/open_webui/routers/workos.py:838)) — and `emit_to_users` ([socket/main.py:283](backend/open_webui/socket/main.py:283)) just looped `sio.emit` to `user:{id}` with **no visibility check**. The payload carries `task_id, task_key, task_title, workstream_id, actor_name` ([:826–828](backend/open_webui/routers/workos.py:826)) plus a **140-char body snippet** only on comment paths ([:830–831](backend/open_webui/routers/workos.py:830)).

`notify()` now filters every recipient through `can_see_workstream` (or `is_app_admin`) before inserting a notification row or emitting to the per-user room (closes G3 + G4). Gating is **consistent** across all callers:

| Caller | Type | Visibility-filtered? |
|---|---|---|
| `create_comment` mentions ([:1051–1056](backend/open_webui/routers/workos.py:1051)) | `mentioned` | **YES** — filtered via `can_see_workstream` |
| `update_comment` new mentions ([:920–923](backend/open_webui/routers/workos.py:920)) | `mentioned` | **YES** |
| `create_comment` parent author ([:1057–1061](backend/open_webui/routers/workos.py:1057)) | `replied` | **YES** — own `WORKOS_RULES.notifications` toggle key (unset ⇒ default-enabled, same as every type); recipient is `parent.user_id`, excluded when already in `mentioned` (precedence: mentioned > replied > commented, one notification per recipient) |
| `create_comment` participants ([:1062–1064](backend/open_webui/routers/workos.py:1062)) | `commented` | **YES** — `_participants` set filtered by `can_see_workstream` before `notify()` (closes G4); excludes both `mentioned` and `replied_to` |
| `create_task` ([:629–630](backend/open_webui/routers/workos.py:629)) | `assigned` | **YES** — `validate_assignees` ensures only visible members reach `notify()` (closes G3) |
| `update_task` ([:668–669](backend/open_webui/routers/workos.py:668)) | `assigned` | **YES** |
| `update_task` ([:670–673](backend/open_webui/routers/workos.py:670)) | `status_changed` | **YES** |

The per-user notification channel is now consistent with Channel A: non-members do not receive task metadata or comment snippets for workstreams they cannot see.

---

## 6. Frontend consumption

The WorkOS frontend has **no authoritative access model of its own** — it is a pure consumer that trusts the backend for all enforcement. All frontend gating is **cosmetic** (show/hide); every action is re-checked server-side.

- **Role source:** `/bootstrap` returns a flat `roles: Record<teamId, TeamRole>` map, stored in the `roles` Svelte store ([store.ts:26](src/lib/components/workos/lib/store.ts), set in `loadBootstrap` [:82–104](src/lib/components/workos/lib/store.ts)). The WorkOS-level capability gate (`features.workos` / `features.workos_admin`) is read from the Open WebUI `user` store, not the roles map.
- **Tree is server-trimmed:** `/bootstrap` already filters restricted workspaces/workstreams ([workos.py:170](backend/open_webui/routers/workos.py:170)), so the sidebar never re-checks visibility.
- **Predicates:** `lib/roles.ts` exposes pure predicates — `canManageTeam` (owner only), `canManageMembers` / `canCreateWorkspace` (owner||admin), `canDeleteTask` (creator OR owner/admin), `canDeleteComment` / `canDeleteAttachment` (author OR owner/admin), `canUseAdmin` (reads OWUI `user.role==='admin' || permissions.features.workos_admin`). `canManageWorkspace` is defined+tested and **used by `canEditTask`/`canEditSubtask`** (roles.ts:68).
- **Nav gate:** `railItems.ts` shows the WorkOS item if `user.role==='admin' || permissions.features.workos ?? true` (defaults visible, mirroring backend default-ON).
- **Admin view guard** is client-side only — `WorkOSApp.svelte` snaps the view from `admin` back to `board` when `!canUseAdmin` (cosmetic; the server re-checks everything).
- **Sidebar access management** (`chrome/access/`, since 2026-07-02, replaces the Access
  console page): workspace rows and the team card carry kebab (⋯) + right-click menus,
  gated by `canManageMembers(teamRole) || app-admin`, opening `TeamSettingsDialog`
  (members roster + rename/archive/delete, owner-only General tab) and
  `WorkspaceSettingsDialog` (visibility flip + restricted-members + rename/delete).
  All mutations go through the existing gated endpoints — role gates, the last-owner
  guard, and realtime emit/eviction come from the server unchanged. UI mirrors:
  owner-grant selects disabled for non-owners, last-owner row locked,
  restricted-workspace add-picker sourced from team members only, and the
  `team→restricted` flip sits behind a destructive-confirm dialog
  (`RestrictConfirmDialog`, shared by the dialog and the sidebar quick-flip). The flip
  can evict the acting admin's own client (non-member, non-creator) — the dialog
  detects the workspace vanishing from bootstrap and closes. Restricted rows show a
  lock badge (visibility ships in `/bootstrap`).
- **Pickers source the team-wide `directory` store** — both `AssigneeField` and the `@mention` composer offer users who may not see a restricted workspace; the backend now validates each `assignee_id` against `can_see_workstream` and rejects invisible ids (G1 closed), and the mention *notification* is filtered server-side.
- **Workspace visibility is editable in the UI** — set at create time in `ModalHost`, flipped via `api.updateWorkspace({visibility})` from `WorkspaceSettingsDialog.svelte` (destructive confirm on `team→restricted`) or the sidebar quick-flip. Restricted workspaces show a lock badge on their sidebar rows (visibility ships in `/bootstrap`).
- **URL deep links (2026-07-20)** — `/workos?view=…&ws=…&task=…` (urlSync.ts) adds
  NO frontend access logic: `ws` is validated against the server-trimmed bootstrap
  tree, `task` resolves via `GET /tasks/{id}` (404 for missing AND forbidden — one
  client fallback path, no exists/forbidden oracle). Pasting `?view=admin` without
  the permission is snapped away by the existing WorkOSApp guard.

---

## 7. Config / feature flag

WorkOS is gated by **two per-user permission flags**, not a global switch. Global admins (`role=='admin'`) bypass both.

| Flag | Default | Source | Enforced by |
|---|---|---|---|
| `features.workos` | **True (ON)** | `USER_PERMISSIONS_FEATURES_WORKOS` env ([config.py:1578–1580](backend/open_webui/config.py:1578)), wired at [:1662](backend/open_webui/config.py:1662) | `require_workos` → `401` ([workos.py:52](backend/open_webui/routers/workos.py:52)) |
| `features.workos_admin` | **False (OFF)** | `USER_PERMISSIONS_FEATURES_WORKOS_ADMIN` env ([config.py:1582–1584](backend/open_webui/config.py:1582)), wired at [:1663](backend/open_webui/config.py:1663) | `require_workos_admin` → `403` ([workos.py:59](backend/open_webui/routers/workos.py:59)) |

Both live inside the `USER_PERMISSIONS` `PersistentConfig` ([config.py:1670–1674](backend/open_webui/config.py:1670)) so they can be overridden per group. `has_permission` resolves the dotted key across group permissions then the default tree ([access_control/__init__.py:71–104](backend/open_webui/utils/access_control/__init__.py)).

### `WORKOS_RULES` (`PersistentConfig` key `workos.rules`, [config.py:1676–1685](backend/open_webui/config.py:1676))
Default `{"team_creation": "all_users", "default_workspace_visibility": "team"}`. Accepted keys:

| Key | Values | Consumed by |
|---|---|---|
| `team_creation` | `all_users` \| `admins_only` | `create_team` → `403` for non-admin when `admins_only` ([workos.py:193–195](backend/open_webui/routers/workos.py:193)) |
| `default_workspace_visibility` | `team` \| `restricted` | `create_workspace` uses this as the fallback when `form.visibility` is absent (closes G8) |
| `notifications` | `{type: bool}` | `_notif_enabled` ([workos.py:807–810](backend/open_webui/routers/workos.py:807)) |
| `max_attachment_mb` | int ≥ 0 (default 25) | `_max_attachment_bytes` ([workos.py:961–964](backend/open_webui/routers/workos.py:961)) |

**Registration (load-bearing):** `app.state.config.WORKOS_RULES = WORKOS_RULES` at [main.py:927](backend/open_webui/main.py:927) (imported [:414–415](backend/open_webui/main.py:414)). Before this line existed, any endpoint touching `WORKOS_RULES` raised `AttributeError` at runtime (the historical Phase-1 smoke-test bug). There is currently **no automated test** exercising `request.app.state.config.WORKOS_RULES` end-to-end, so a regression dropping line 927 would only surface in manual smoke.

---

## 8. Gaps — elements that SHOULD use access control but don't

Only **verified** gaps (`VERIFICATION.confirmedGaps`, both verifiers merged + deduped). Suspected-but-debunked items are excluded: realtime workstream/team room gating, attachment-download gating, and mention-notification filtering were all **confirmed correct** and are *not* gaps.

### HIGH

✅ **Closed (2026-06-27, commit e505dd998 + ad91135f0)**

**G1 — `assignee_ids` never validated against visibility (create_task & update_task).**
`create_task` ([workos.py:614–631](backend/open_webui/routers/workos.py:614)) and `update_task` ([workos.py:643–674](backend/open_webui/routers/workos.py:643)) store the raw id list (model: `assignee_ids = Column(JSON, default=list)`, [models/workos.py:470](backend/open_webui/models/workos.py:470)) and call `notify()` per id. `_validate_task_fields` ([workos.py:589–599](backend/open_webui/routers/workos.py:589)) validates only status/priority/progress/dates — never membership.
*Risk:* a user who can see one `team`-visibility workspace can assign **any** app user (ids harvested from `GET /users`) to a task, pushing the task's id/key/title/workstream_id into a stranger's notification inbox and surfacing them in assignee/avatar UI — for a task they then get `404` opening. Information disclosure + spam, inconsistent with the mention path which *does* filter.
*Fix:* validate each id with `can_see_workstream(id, False, task.workstream_id)` before insert/update **and** before `notify()`; reject or drop failing ids. Prefer rejecting — an assignee who can't see the task is a data-model bug, not just a notification bug.

✅ **Closed (2026-06-27, commit 4f7ef4b78)**

**G2 — `PATCH /tasks/{id}` has no write/role gate beyond visibility.**
The handler stops at `require_task_visible` ([workos.py:643/649](backend/open_webui/routers/workos.py:643)) — no creator/assignee/manager check before `Tasks.update_fields` ([:653](backend/open_webui/routers/workos.py:653)). Contrast `delete_task` ([:684–686](backend/open_webui/routers/workos.py:684)) which gates on creator-or-admin.
*Risk:* in any `team`-visibility workspace, **every team member** can mutate every field (title, description, status, priority, `assignee_ids`, labels, dates, progress, sort_key) of tasks they neither created nor are assigned to. No notion of an editor role.
*Fix:* decide a write policy; if broad editing is intended for team-visible workspaces, document it — otherwise gate sensitive mutations (`assignee_ids`, status, labels) to creator/assignee/workspace-manager, mirroring `delete_task`.

✅ **Closed (2026-06-27, commit 902d9b7c5)**

**G3 — `assigned` + `status_changed` notifications leak task metadata to non-members.**
`notify()` ([workos.py:817–838](backend/open_webui/routers/workos.py:817)) has no internal `can_see_workstream` check; callers pass recipients straight through — `assigned` on create ([:629–630](backend/open_webui/routers/workos.py:629)) and update ([:668–669](backend/open_webui/routers/workos.py:668)), and `status_changed` to `{created_by_id, *assignee_ids}` ([:670–673](backend/open_webui/routers/workos.py:670)). Delivered both as a persisted row (returned by `GET /notifications`) and over the per-user realtime room.
*Risk:* a non-member assignee (or a creator who has since lost workspace visibility) receives `task_id, task_key, task_title, workstream_id, actor_name` for a workstream they cannot open. (Same root cause as G1.)
*Fix:* filter recipients through `can_see_workstream` inside `notify()` (or at each task-notify call site), or — preferably — fix assignment validation at the source per G1. Make the access decision **before** the best-effort `try/except` so a check failure fails closed.

### MEDIUM

✅ **Closed (2026-06-27, commit 902d9b7c5)**

**G4 — `commented` notification leak with comment-body snippet.**
`create_comment` notifies `_participants(task)` ([workos.py:894–896](backend/open_webui/routers/workos.py:894)) — creator + assignees + all prior comment authors + all users previously @mentioned ([_participants :842–851](backend/open_webui/routers/workos.py:842)) — with no current-visibility re-check, and the payload includes a 140-char body snippet ([:830–831](backend/open_webui/routers/workos.py:830)).
*Risk:* a participant who lost workspace visibility (or a stale assignee per G1) still receives **comment content** for a stream they can no longer see. `_participants` accumulates every historical mentioner, widening the leak over the task's life.
*Fix:* filter the participants set through `can_see_workstream` before the `commented` `notify`, mirroring the mention-path filter.

✅ **Closed (2026-06-27, commit c69edb809 + 86b2875ae)**

**G5 — `PATCH /subtasks/{id}` has no author/role gate.**
Stops at `require_subtask_visible` (== task visibility) ([workos.py:1128/1134](backend/open_webui/routers/workos.py:1128)); no creator/author/role check before `Subtasks.update_fields` ([:1140](backend/open_webui/routers/workos.py:1140)).
*Risk:* any task-visible user can rename, complete/reopen, or reorder any subtask (including ones they didn't create); changes mirror into parent task progress.
*Fix:* apply the author-or-team-owner/admin guard used by `delete_comment`/`delete_attachment`, or document subtasks as collaboratively editable.

✅ **Closed (2026-06-27, commit c69edb809 + 86b2875ae)**

**G6 — `DELETE /subtasks/{id}` has no author/role gate.**
Stops at `require_subtask_visible` ([workos.py:1155/1160](backend/open_webui/routers/workos.py:1155)); no gate before `Subtasks.delete` ([:1161](backend/open_webui/routers/workos.py:1161)), unlike `delete_comment`/`delete_attachment`.
*Risk:* any task-visible user can delete any subtask.
*Fix:* add an author-or-team-owner/admin guard, or document subtasks as collaboratively deletable.

✅ **Closed (2026-06-27, commit ecb276d0b)**

**G7 — `GET /users` returns the entire app roster with no team scoping.**
`require_workos` then `list_all_users()` → full id+name roster ([workos.py:148–154](backend/open_webui/routers/workos.py:148)), broader than the team-scoped `/directory`.
*Risk:* user enumeration to any WorkOS-enabled user; also the id source feeding G1.
*Fix:* acceptable only if `assignee_ids`/mentions are properly visibility-gated; otherwise scope the picker to team co-members like `/directory`, or gate behind a higher role.

✅ **Closed (2026-06-27, commit 8f77ccc88)**

**G8 — `default_workspace_visibility` rule is validated but never applied.**
`create_workspace` ([workos.py:349–356](backend/open_webui/routers/workos.py:349)) uses `form.visibility` (schema default `'team'`, [:290](backend/open_webui/routers/workos.py:290)) — the admin-configured `WORKOS_RULES.default_workspace_visibility` ([config.py:1682](backend/open_webui/config.py:1682), validated [workos.py:787–788](backend/open_webui/routers/workos.py:787)) has no effect.
*Risk:* config advertises a setting that does nothing; admins assuming new workspaces default to `restricted` get `team`.
*Fix:* apply the rule as the fallback when `form.visibility` is unset, or remove the key + its validation/test.

### LOW

✅ **Closed (2026-06-27, commit 448fc49fe)**

**G9 — `remove_member` has no last-owner / self-lockout guard.**
`require_team_role({'owner','admin'})` checks only the actor's role, not whether the removal leaves the team ownerless ([workos.py:271–278](backend/open_webui/routers/workos.py:271)).
*Risk:* a team can be left with no owner; an owner can lock themselves out.
*Fix:* reject removal of the final owner.

✅ **Closed (2026-06-27, commit fa4ad6a1b)**

**G10 — `GET /notifications` `limit` (and `before`) unbounded.**
Forwarded straight to the DAO ([workos.py:1064–1070](backend/open_webui/routers/workos.py:1064)).
*Risk:* oversized result pulls.
*Fix:* clamp, e.g. `min(limit, 200)`.

✅ **Closed (2026-06-27, commit 0525fbad6)**

**G11 — `upload_attachment` accepts any MIME and an unvalidated `comment_id`.**
`file.content_type` stored verbatim with no allowlist; `comment_id` ([workos.py:967–995](backend/open_webui/routers/workos.py:967)) passed to `Attachments.insert` without checking it belongs to `task_id`.
*Risk:* arbitrary content type; attachment associable with a foreign comment.
*Fix:* add a content-type/extension allowlist (or sanitized download) and verify `Comments.get_by_id(comment_id).task_id == task_id` before insert.

> **Unverified (not promoted to a gap):** the claim that `Notifications.mark_read` filters the supplied `ids` by owner in the DAO was not confirmed at the DAO body — only that the router passes `user.id` ([workos.py:1073](backend/open_webui/routers/workos.py:1073)). The endpoint-layer scoping is correct; the DAO-level `id` filtering is an assumption worth confirming, not a known leak.

---

## 9. Per-workstream visibility — CONSIDERED & DECLINED (2026-06-26)

> **DECISION (2026-06-26):** We will **NOT** add per-workstream visibility. Private areas
> are modeled with **restricted Workspaces + explicit membership** (the mechanism that already
> exists). The owner-bypass question (a) was settled **No** — even team owners must be explicit
> members of a restricted area; only the app-level admin is a super-user (unchanged from today).
> The design below is retained as a record of the considered approach in case it is revisited.
>
> Consequence of this decision: because confidentiality now rests entirely on restricted
> Workspaces, the leak gaps **G1 / G3 / G4** (§8) and the §5 "structural scoping mismatch"
> caveat become higher priority — they let task metadata (and comment snippets) reach
> non-members of a restricted Workspace via assignment and the per-user notification channel,
> partially defeating the restriction. The follow-up work is therefore *completing + hardening
> restricted Workspaces*, not adding a new layer.

**(Declined) direction:** push the visibility boundary **down one level** from Workspace to Workstream so a workstream can be hidden from team members who can see its parent.

1. **Add `WorkosWorkstream.visibility`** (`'team' | 'restricted'`, default `'team'`) mirroring `WorkosWorkspace.visibility` ([models/workos.py:68](backend/open_webui/models/workos.py:68)), plus the corresponding field on `WorkstreamModel` ([:146–155](backend/open_webui/models/workos.py:146)).
2. **Add a `WorkosWorkstreamMember` table** mirroring `WorkosWorkspaceMember` ([:75](backend/open_webui/models/workos.py:75)) — `(workstream_id, user_id, role)`, unique on `(workstream_id, user_id)`.
3. **Re-point `can_see_workstream`** ([models/workos.py:1108](backend/open_webui/models/workos.py:1108)) at the workstream's own visibility + member rows instead of (or in addition to) the workspace's. The router twin `require_workstream_visible` ([workos.py:463](backend/open_webui/routers/workos.py:463)) follows.
4. **Retire / collapse the Workspace layer** — once visibility lives on the workstream, the Workspace becomes a grouping container; the `Workspace.visibility` switch and `WorkosWorkspaceMember` are candidates for removal/merge.

**Decisions still open** (must be settled before implementation):
- **(a) Team owner/admin bypass of restriction.** Today a *team* owner/admin gets **no** bypass of a restricted gate — only the app-level `is_admin` flag does ([models/workos.py:1119](backend/open_webui/models/workos.py:1119), [workos.py:318](backend/open_webui/routers/workos.py:318)). Decide whether team owners/admins should implicitly see all restricted workstreams in their team (would require a role-aware check in the shortcut).
- **(b) Couple the assignee/mention picker to workstream membership.** This eliminates the assign-then-`404` dead-end (G1) at the UX level by only offering users who can see the workstream, and pairs with the server-side `can_see_workstream` validation on `assignee_ids`.
- **(c) Move the bootstrap visibility filter down to per-workstream.** The inline workspace filter at [workos.py:170](backend/open_webui/routers/workos.py:170) must be reworked (and ideally de-duplicated against the shared `workspace_visible`/`can_see_*` predicates) so the bootstrap payload pre-loads exactly the per-workstream slice the caller may see, keeping the request path and notification/realtime gates a single source of truth.