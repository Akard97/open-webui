# WorkOS — Task Create Dialog + Attachment-Required-to-Complete (Design)

> Approved 2026-07-15 (branch `osool`). Two features: (1) every "add task" entry point
> opens a create dialog where only **title + at least one assignee** are mandatory;
> (2) a per-task **"require attachment to complete"** flag, set by the creator, that
> hard-blocks moving the task to `done` until the task has at least one attachment.

## 1. Context & motivation

Today there is no create form at all: every entry point is a title-only quick-add
input (board top, board per-column, list group add, list global add, timeline add),
submitting via `store.addTask` → `POST /workstreams/{id}/tasks`. Tasks are therefore
routinely created with no assignee, and there is no way to demand proof-of-work
(an attachment) before a task can be completed.

Decisions locked with the user:

| Question | Decision |
|---|---|
| Assignee rule at create | **Min 1 assignee, multi-select still allowed** (multi-assignee feature intact) |
| Flag control | **Creator (and app-admin), at create time and later from task detail** |
| Enforcement | **Hard block, everywhere** — server rejects status→`done` with no attachment |
| Entry points | **Dialog everywhere** — all quick-adds replaced by the dialog |
| Subtasks | **Untouched** — title-only quick-add stays; no assignee rule, no flag |

## 2. Feature 1 — Task create dialog

### Component

New `src/lib/components/workos/views/TaskCreateDialog.svelte`, built from shadcn-svelte
primitives (Dialog) + existing WorkOS field components (assignee multi-select picker
sourced from the `directory` store, status/priority selects, date inputs, labels picker).
Mounted once (WorkOSApp/ModalHost level), opened via a store-level
`openTaskCreate(prefill)` call.

Fields, in order:

1. **Title** — text, autofocus, required.
2. **Assignees** — multi-select, required (min 1). Same picker as task detail.
3. Description — optional.
4. Status — optional, prefilled from context (defaults to first/backlog status).
5. Priority — optional.
6. Start / Due dates — optional, prefilled from timeline context.
7. Labels — optional.
8. **Require attachment to complete** — checkbox, default off (feature 2).

Create button disabled until title non-empty and ≥1 assignee; inline hint on the
assignee field when empty. Escape / cancel closes without creating.

A static HTML mockup of the dialog is produced and shown to the user **before**
implementation (per the WorkOS design-taste rule).

### Entry points (all open the dialog, quick-add inputs removed)

| Trigger | Prefill |
|---|---|
| Board top "Add task" | default status |
| Board column "+" | that column's status |
| List group add | that group's value (status) |
| List global add | none (backlog defaults) |
| Timeline add | auto start/due dates from the clicked slot |

Subtask creation (`SubtasksPanel`) is explicitly out of scope and keeps its
title-only quick-add.

### Validation

- **Client:** disabled submit + inline hints (cosmetic).
- **Server (source of truth):** `TaskCreateForm` gains `assignee_ids` min-length-1
  validation → `400` when empty/absent. Existing `validate_assignees` visibility
  check (G1 closure) still runs after.
- **PATCH:** editing assignees later stays allowed, but a patch that would clear
  `assignee_ids` to empty is rejected `400` (the rule stays meaningful post-create).

## 3. Feature 2 — `attachment_required` flag

### Data model

- New column `WorkosTask.attachment_required` — `Boolean`, `nullable=False`,
  `server_default` false.
- Alembic migration, down-revision `d6e7f8a9b0c1` (workos timestamps → ms).
- Field added to `TaskCreateForm`, `TaskUpdateForm`, `TaskModel` (rides along in
  every task payload, board/list/detail alike).

### Permission — who can toggle

New entry in the `CAPABILITIES` registry (`backend/open_webui/utils/workos_access.py`):

| Capability | Rule order | Used by |
|---|---|---|
| `task.flag.attachment_required` | app-admin → task creator | `PATCH /tasks/{id}` when the patch touches `attachment_required` |

Notes:
- Assignees / workspace managers may edit other task fields (existing
  `require_task_writable`) but **not** this flag.
- Legacy tasks with `created_by_id IS NULL` → only app-admin can toggle.
- At create time no extra check is needed — the creator is the caller.
- The access-control reference doc (`2026-06-26-workos-access-control.md` §4
  capability table) is updated in the same change (standing rule).

### Enforcement — hard block on completion

In `update_task` (`PATCH /tasks/{id}`), after visibility/writability gates:

- If the patch sets `status == 'done'` **and** the task's effective
  `attachment_required` is true (effective = the value in this patch when the patch
  includes the field, else the stored value) **and** the task has zero attachment rows
  (task-level `comment_id IS NULL` **and** comment-level rows both count) →
  `400` with `detail` code `ATTACHMENT_REQUIRED`.
- Guard fires **only on the transition to `done`**. Deleting attachments after
  completion does not reopen the task; toggling the flag on a done task has no
  retroactive effect.
- Order: the flag-toggle capability check and the done-guard both run before any
  field is persisted, so a mixed patch (e.g. `{status: 'done', attachment_required: …}`)
  fails atomically.

### Frontend UX

- **Store:** `editTask` gains rollback-on-error — on a `400 ATTACHMENT_REQUIRED`
  response the optimistic status change is reverted and a toast shows
  "Attachment required before completing this task."
- **Task detail:** attachments are already loaded there, so the status dropdown
  pre-checks — the `done` option shows a paperclip hint/tooltip when the flag is
  on and count is 0. Creator/app-admin see the "Require attachment" toggle in the
  properties area; everyone else sees a read-only badge.
- **Board/list cards:** small paperclip-required indicator when the flag is on
  (cards don't know attachment counts — server is the enforcer; a rejected
  drag-to-done snaps back with the toast).

## 4. Realtime / notifications

Nothing new. Existing `task.created` / `task.updated` room events already carry the
full task payload, so the flag propagates. No new notification type.

## 5. Error handling summary

| Case | Behavior |
|---|---|
| Create with empty `assignee_ids` | `400` server; client button disabled anyway |
| Patch clearing assignees to `[]` | `400` |
| Non-creator/non-admin toggles flag | `403` (capability detail string) |
| Status→done, flag on, 0 attachments | `400 ATTACHMENT_REQUIRED`; client rollback + toast |
| Legacy task, `created_by_id` null | flag toggle admin-only |

## 6. Testing

- **Backend (pytest):** create-form validation (empty/missing assignees → 400);
  patch-to-empty-assignees → 400; flag-toggle permission matrix (creator ✓,
  app-admin ✓, assignee ✗, workspace manager ✗, team owner ✗); done-guard
  (blocked at 0 attachments, allowed with task-level attachment, allowed with
  comment-level attachment, flag-off unaffected, non-done transitions unaffected);
  mixed patch atomicity.
- **Frontend (vitest):** store `editTask` rollback on 400; `addTask` payload carries
  `assignee_ids` + `attachment_required`.
- **Browser smoke** at the end (all five entry points, prefill correctness, drag-to-done
  rejection, detail toggle visibility).

## 7. Out of scope

- Subtask create dialog / subtask assignees.
- Blocking archive/delete on the flag.
- Retroactive enforcement on already-done tasks.
- "My Work" as a create entry point (none exists today).
