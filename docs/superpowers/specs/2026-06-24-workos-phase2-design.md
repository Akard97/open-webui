# WorkOS — Phase 2 Design (Collaboration & Notifications)

**Date:** 2026-06-24
**Status:** Approved (design); pending spec review
**Builds on:** [Phase 1](2026-06-22-workos-phase1-design.md) (core spine + realtime + admin center)
**Pattern reference:** Policy Review (`models/policy_review.py`, `routers/policy_review.py`) and the existing WorkOS Phase 1 code.

---

## 1. Overview

Phase 2 adds the **collaboration layer** to WorkOS: task comments (markdown),
file attachments, an automatic activity log, @mentions, and a notification
system with an in-tool inbox. It turns each task from a static record into a
place where a team discusses, shares files, and stays informed.

It is built entirely on the Phase 1 foundation: the same DAO/router/socket
patterns, the same membership-scoped authorization, and the existing Socket.IO
infrastructure (workstream rooms + the per-user `emit_to_users` helper).

This document covers **Phase 2 only**. Phase 3 (My Work dashboard, Timeline/Gantt,
saved views, and the workspace/workstream realtime carry-over) is out of scope.

---

## 2. Goals & non-goals

### Phase 2 goals
- **Comments** on tasks: markdown body, flat chronological list, author can edit/delete own (admins can delete any). Inline @mentions.
- **Attachments**: any file type, attachable at the task level *and* within a comment; image thumbnails. Stored via OWUI's `Storage` provider, downloads gated by WorkOS task visibility.
- **Activity log**: automatically generated entries for task changes (status, assignee, priority, due date, completion, title/description edits, comment added, attachment added).
- **Combined timeline**: the task-detail panel shows comments and activity interleaved in one chronological feed, with a comment composer at the end.
- **@mentions**: mention any member who can see the task; mentions drive notifications and render as links.
- **Notifications**: generated on assignment, @mention, comment on a task you participate in, and status/completion changes on tasks you created or are assigned to. Delivered live (per-user socket) to an in-tool **Inbox** with a live unread badge on the WorkOS sidebar.
- **Admin**: a Notifications section in the Admin Center to globally toggle notification categories and set the max attachment size.

### Non-goals (Phase 2)
- My Work dashboard, Timeline/Gantt view, saved views, filters/search/display options (Phase 3).
- Workspace/workstream realtime carry-over (the half-wired nav events from Phase 1 — Phase 3).
- Threaded/nested comment replies (flat only).
- Reactions/emoji on comments, comment pinning.
- An explicit subscribe/unsubscribe (watch) model — "participants" are derived on the fly (§7).
- A **global left-rail badge** while the user is elsewhere in the app (e.g. in chat). Deferred to keep WorkOS self-contained per the Osool rebrand scoping; the live badge ships on the WorkOS sidebar Inbox entry only. See §10.
- OS-level / web-push / desktop notifications. In-app inbox + live badge only.

---

## 3. Decisions (locked)

| Topic | Decision |
|---|---|
| Comment richness | Markdown, flat list, edit/delete own (admins delete any), inline @mentions |
| Attachment scope | Task-level **and** comment-level; any file type; image thumbnails |
| Attachment storage | OWUI `Storage` provider for bytes; WorkOS-owned `workos_attachment` row; downloads gated by WorkOS task visibility (not OWUI file ACL) |
| Activity presentation | One combined timeline (comments + system activity) in the detail panel |
| Notification triggers | Assigned · @mentioned · comment on a participated task · status/done change on your task |
| Notification delivery | In-app Inbox + live unread badge on the WorkOS sidebar, pushed via `emit_to_users` |
| Subscriptions | Derived participants (no watch table) |
| Global rail badge | Deferred (sidebar Inbox badge only) |

---

## 4. Architecture & file layout

Extends the Phase 1 layout; no new top-level structure.

### Backend
- `backend/open_webui/models/workos.py` — add tables, Pydantic models, and DAOs for comment, attachment, activity, notification. Add notification fan-out + activity-generation helpers (or a small `internal/workos/` helper module if `workos.py` grows large — see §13).
- `backend/open_webui/routers/workos.py` — add comment, attachment, activity, and notification endpoints (§6); extend `/bootstrap` with the unread count; extend `/admin/settings`.
- `backend/open_webui/socket/main.py` — emit the new room events; use the existing `emit_to_users` (line ~283) for per-user notification delivery. No new subscribe handler needed (comment/activity/attachment events ride the existing `workos:workstream:{id}` room).
- `backend/open_webui/config.py` — `PersistentConfig` for notification category toggles and `WORKOS_MAX_ATTACHMENT_MB`. **Must also be registered on `app.state.config` in `main.py`** (Phase 1 lesson — see §11).
- Alembic migration adding the four Phase 2 tables. `down_revision = 'f0a1b2c3d4e5'` (current head, the Phase 1 WorkOS migration).
- `backend/open_webui/test/workos/` — pytest for the new surface (§12).

### Frontend (`src/lib/components/workos/`)
- `views/TaskDetail.svelte` — replace the "Comments & activity arrive in Phase 2" stub (line ~111) with the combined feed + composer + a task-level Files section.
- `views/detail/Feed.svelte` — merges comments + activity into one chronological list.
- `views/detail/CommentItem.svelte` — renders a markdown comment, author, timestamp, edit/delete affordances.
- `views/detail/ActivityItem.svelte` — renders a system activity line ("X moved this to In Progress").
- `views/detail/CommentComposer.svelte` — markdown textarea + @mention autocomplete + attach button.
- `views/detail/AttachmentList.svelte` — task/comment attachments with thumbnails + download/delete.
- `views/InboxView.svelte` — notifications list, mark read / mark-all-read, click-through to the task.
- `chrome/Sidebar.svelte` — Inbox entry with live unread badge.
- `lib/api.ts` — typed wrappers for the new endpoints.
- `lib/store.ts` — comment/activity/attachment stores keyed by the open task; notifications store + unread count; realtime handlers for the new events.
- `lib/mentions.ts` (+ `mentions.test.ts`) — pure parser: extract @mentions from a markdown body → user ids; resolve ids → display tokens.
- `views/admin/` — Notifications section (in `RulesTab.svelte` or a new tab).

---

## 5. Data model (Phase 2 tables)

Conventions match Phase 1: `Text` UUID ids; `created_at`/`updated_at`/`edited_at` are
nanosecond epochs via `int(time.time_ns())`; user references are `Text` FKs to `user.id`
(not enforced as DB FKs).

### `workos_comment`
| col | type | notes |
|---|---|---|
| id | Text PK | |
| task_id | Text | |
| user_id | Text | author → `user.id` |
| body | Text | markdown |
| mentions | JSON | array of `user.id` parsed from `body` at write time |
| edited_at | BigInteger nullable | set on edit |
| created_at / updated_at | BigInteger | |

### `workos_attachment`
| col | type | notes |
|---|---|---|
| id | Text PK | |
| task_id | Text | owning task |
| comment_id | Text nullable | null = task-level; set = posted within a comment |
| storage_key | Text | key/path returned by the `Storage` provider |
| name | Text | original filename (for display) |
| size | BigInteger | bytes |
| content_type | Text nullable | mime type |
| created_by_id | Text | uploader → `user.id` |
| created_at | BigInteger | |

### `workos_activity`
| col | type | notes |
|---|---|---|
| id | Text PK | |
| task_id | Text | |
| team_id | Text | denormalized (scoping / future cross-task queries) |
| user_id | Text | actor → `user.id` |
| type | Text | `created` / `status_changed` / `assignee_changed` / `priority_changed` / `due_changed` / `completed` / `reopened` / `comment_added` / `attachment_added` / `title_changed` / `description_changed` |
| data | JSON | change payload, e.g. `{ "from": "todo", "to": "in_progress" }` |
| created_at | BigInteger | |

### `workos_notification`
| col | type | notes |
|---|---|---|
| id | Text PK | |
| user_id | Text | recipient → `user.id` |
| actor_id | Text | who caused it |
| task_id | Text nullable | the task it concerns |
| comment_id | Text nullable | |
| type | Text | `assigned` / `mentioned` / `commented` / `status_changed` |
| data | JSON | render snapshot: task key/title, comment snippet, from/to — so the inbox renders without joins |
| read | Boolean | default false |
| created_at | BigInteger | |

No watch/subscription table (see §7). No schema changes to Phase 1 tables.

---

## 6. API surface (additions under `/api/v1/workos`)

Every route resolves the requesting user and enforces §8. Responses are Pydantic models.

### Comments
- `GET /tasks/{id}/comments` — list (chronological); requires task visibility.
- `POST /tasks/{id}/comments` — `{ body }`; parses mentions, writes the comment, generates `comment_added` activity, runs notification fan-out, emits realtime.
- `PATCH /comments/{id}` — `{ body }`; author only; re-parses mentions, sets `edited_at`; notifies any newly-added mentions.
- `DELETE /comments/{id}` — author or team/workspace admin.

### Attachments
- `POST /tasks/{id}/attachments` — multipart upload, optional `comment_id`; stores via `Storage`, writes the row, generates `attachment_added` activity, emits realtime. Rejects over `WORKOS_MAX_ATTACHMENT_MB`.
- `GET /tasks/{id}/attachments` — list for the task.
- `GET /attachments/{id}/content` — **gated download**: checks WorkOS task visibility, then streams the bytes from `Storage` (sets `Content-Disposition` + `content_type`).
- `DELETE /attachments/{id}` — uploader or admin; removes the row and the stored object.

### Activity
- `GET /tasks/{id}/activity` — list (chronological); requires task visibility. The client merges comments + activity into the timeline (no separate combined endpoint).

### Notifications
- `GET /notifications?unread_only=<bool>&limit=&before=` — current user's notifications, newest first.
- `POST /notifications/read` — `{ ids?: string[], all?: bool }`; marks read; returns the new unread count.
- `GET /bootstrap` (extended) — include `notifications_unread` so the badge is correct on first paint.

### Admin
- `GET /admin/settings` / `PATCH /admin/settings` (extended) — notification category toggles + max attachment size.

User picker / directory for @mention autocomplete reuses the existing directory call already used by Phase 1 (`lib/store.ts` `directory`).

---

## 7. Notification fan-out (server-side, after the mutation commits)

Computed in a helper invoked by the task PATCH / comment POST routes. The **actor is
never notified of their own action**, and global category toggles (§9) gate each type.

- **`assigned`** — when `assignee_id` changes to U and U ≠ actor → notify U.
- **`mentioned`** — for each newly-mentioned user who can see the task and ≠ actor → notify (on comment create and on edit, only for mentions not present before).
- **`commented`** — on a new comment, notify the **participant set** minus the actor and minus anyone already receiving a `mentioned` notification for that comment.
- **`status_changed`** — on status change or completion, notify the task creator and assignee (≠ actor).

**Participant set** (derived, no table): `task.created_by_id` ∪ `task.assignee_id` ∪ distinct authors of existing comments ∪ users mentioned on the task. Computed per event.

Each created notification is delivered live via
`emit_to_users('workos:notification.created', payload, [recipient_id])`.

---

## 8. Authorization (extends Phase 1 §6)

Server is the source of truth; `lib/roles.ts` mirrors for UI affordances.

| Action | Allowed |
|---|---|
| Read comments / activity, download attachment | anyone who can see the task |
| Add comment / add attachment | any member who can see the task |
| Edit comment | author |
| Delete comment | author **or** team/workspace admin |
| Delete attachment | uploader **or** team/workspace admin |
| Read / mark notifications | recipient only (a user can only see and mark their own) |
| Admin Notifications settings | system admin **or** `features.workos_admin` |

System admins implicitly pass visibility checks (matching Phase 1). Attachment
downloads are authorized through WorkOS task visibility, **not** OWUI's file ACL.

---

## 9. Admin Center — Notifications

Added to the Admin Center (system admin OR `features.workos_admin`), as a section in
`RulesTab.svelte` (or a new `NotificationsTab.svelte`):
- Toggle each notification category globally (`assigned`, `mentioned`, `commented`, `status_changed`).
- Set max attachment size (`WORKOS_MAX_ATTACHMENT_MB`).

Backed by the extended `/admin/settings`. Disabled categories are skipped during fan-out (§7).

---

## 10. Realtime

Reuses the Phase 1 wiring. No new subscribe handler.

### Room events → `workos:workstream:{id}` (existing room)
- `workos:comment.created` / `workos:comment.updated` / `workos:comment.deleted`
- `workos:activity.created`
- `workos:attachment.created` / `workos:attachment.deleted`

Payloads carry `task_id`; the client applies them to the open task's feed (and ignores
them when that task isn't open). Each payload includes `actor_id` so the actor can ignore
its own echo (the optimistic update already applied).

### Per-user delivery (no room)
- `workos:notification.created` via `emit_to_users(event, payload, [recipient_id])`.

### Client (`lib/store.ts`)
- Comment/activity/attachment handlers registered alongside the existing task handlers in `connectRealtime()`; they patch the open-task feed stores.
- A `workos:notification.created` handler maintained while the WorkOS app is mounted: increments the unread count (driving the sidebar badge) and prepends to the inbox store.
- Local comment/attachment posts are optimistic; the server broadcast reconciles by id.

**Scope note:** the live unread badge is on the **WorkOS sidebar Inbox entry**. A global
left-rail badge while the user is in chat/elsewhere is deferred (§2 non-goals); on next
load the count is re-seeded from `/bootstrap`.

---

## 11. Config additions (`config.py`)

- `PersistentConfig` entries: notification category toggles, `WORKOS_MAX_ATTACHMENT_MB`.
- **LESSON (Phase 1):** any new `PersistentConfig` read via `request.app.state.config.X`
  MUST also be registered with `app.state.config.X = X` in `main.py`, or the route 500s
  with `Config key not found`. Mirror the `WORKOS_RULES` registration. Needs a container
  restart to load.

---

## 12. Testing

### vitest (`lib/*.test.ts`)
- `mentions.ts`: parse `@name`/token → user ids; ignore emails/code spans; resolve unknown ids gracefully.
- `store.ts`: reconcile `comment.*` / `activity.created` / `attachment.*` into the open-task feed; ignore events for other tasks; dedupe own echo by `actor_id`/local id; merged-feed chronological ordering; unread-count increment on `notification.created` and decrement on mark-read.

### pytest (`backend/.../test/workos/`)
Backend tests require `backend/.venv/Scripts/python`. conftest creates/drops only `workos_*` tables.
- Comment CRUD authorization (add by any viewer; edit own only; delete own or admin).
- Attachment upload (size cap), list, **download gated by task visibility** (non-member 403), delete by uploader/admin.
- Activity auto-generated on task status/assignee/priority/due/title/description changes, on comment add, on attachment add — with correct `from`/`to`.
- Notification fan-out per trigger: assignment, mention (incl. on edit — only new mentions), comment to participants, status change; **actor never notified**; disabled category skipped; mark-read flips state + recomputes unread count; recipient isolation (can't read another user's notifications).
- Correct socket emits: room events to `workos:workstream:{id}`; `emit_to_users` called with exactly the intended recipients (mocked).

---

## 13. Migration & risks

- One Alembic migration creates the four Phase 2 tables; `down_revision = 'f0a1b2c3d4e5'`. Up/down verified clean.
- **`workos.py` size:** the model file is already large. If comment/attachment/activity/notification DAOs + fan-out push it past a comfortable size, split the notification/activity *logic* into `internal/workos/` (DAOs stay in `models/workos.py`). Decide during implementation; keep modules focused.
- **Attachment storage coupling:** use the `Storage` provider abstraction (local/S3) so attachments follow the deployment's configured backend; never serve through OWUI's file ACL.
- **Mention parsing fidelity:** mentions are parsed server-side at write time and stored on the row, so notification fan-out and rendering agree. The autocomplete only suggests members who can see the task; a mention of a non-visible user is dropped during fan-out.
- **Notification volume:** no batching/digest in Phase 2 (one notification per qualifying event). Acceptable for current team sizes; revisit if noisy.

---

## 14. Out of scope → Phase 3 (sketch)

My Work home (stat cards + assigned-to-you + activity feed), Timeline/Gantt, filters /
search / display options, saved views, and finishing the workspace/workstream realtime
carry-over from Phase 1.
