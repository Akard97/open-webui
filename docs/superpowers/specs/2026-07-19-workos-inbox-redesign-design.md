# WorkOS Inbox Redesign — Design Spec

**Date:** 2026-07-19
**Status:** Approved (brainstorm 2026-07-19; sections 1–3 approved individually)
**Mockup:** `docs/mockups/workos-inbox-mockups.html` — **V4 "Clean Deck"** is the approved
direction: V4 chrome (header, subtitle stats, controls, needs-you cards) with the **V1 feed
anatomy** (icon bubbles, roomy two-line rows, snippet blocks, status-transition chips,
uppercase day rules). V1–V3 remain in the file for reference only.

## 1. Problem

`InboxView.svelte` is a bare flat list: unread dot, one summary line, optional snippet,
"Mark all read". No grouping, no filters, no time context, no task context, no pagination
UI, and clicking a notification navigates away (board view + task drawer), losing inbox
position. The design-system spec (§4) flags the InboxView/My-Work-rail divergence and an
audit bug (Mark-all-read shown on empty inbox).

## 2. Decisions (locked during brainstorm)

| # | Decision |
|---|---|
| D1 | Scope: frontend redesign + small backend (archive state, counts endpoint). |
| D2 | Core model: hybrid dashboard — "Needs you" (unread mentions + assignments) pinned on top, ambient feed below. |
| D3 | Click opens the task **in-place**: desktop split-pane with `TaskDetail` inline right; no view switch. Mobile keeps full-screen detail. |
| D4 | Lifecycle: unread → read → archived. Archive implies read. |
| D5 | Feed: day headers + same-task stacking (consecutive same-task rows within a day collapse to one row + "N updates" pill; expand in place). |
| D6 | Controls: type tabs with counts (All / Mentions / Assigned / Comments / Status), "Unread only" chip-toggle, Archived view, Mark all read. |
| D7 | Visual: V4 Clean Deck — flat white canvas (gray-950 dark), `rounded-lg` hairline cards, no gradients/KPI tiles; stats live in the subtitle + tab counts. Feed rows use the V1 anatomy per user pick (incl. uppercase day headers with rule). |
| D8 | Unread badges switch stray `sky-500` → `bg-primary` in all chrome — Sidebar, NavDrawer, MobileHeader (design-system D1 fix folded in). |

## 3. UX spec (left pane, top to bottom)

- **Header:** `Inbox` (22px/600 tracking-tight) + subtitle line
  `"<b>N need your attention</b> · M more updates · oldest unread <age>"` (13px, gray).
  Counts derive from `notificationCounts` + loaded list; "oldest unread" client-side.
- **Controls row** (13px padding, hairline bottom border):
  - Pill segment tabs (design-system D5: pill segments = view options): All / Mentions /
    Assigned / Comments / Status, each with a count pill (unread, non-archived, from
    `/counts`); active tab count pill uses primary.
  - "Unread only" chip-toggle — the My Work "Need attention" chip pattern (bordered chip
    with embedded mini switch), primary when on.
  - Archived ghost icon-button → switches list to archived view (day-grouped like the
    feed, no needs-you section — archived rows are read so none qualify; hover action =
    Unarchive; back button returns). Entering/leaving archived resets "Unread only"
    (archived rows are always read) and hides the tab count pills (counts describe the
    inbox, not the archive).
  - "Mark all read" ghost button — hidden when nothing unread (audit bug #4 fix).
- **Needs you section:** header 13px/500 with primary @ icon + primary count pill.
  Cards: flat `rounded-lg`, hairline border, 2px primary inset (`box-shadow:inset`),
  avatar 28px, one-line sentence (`<b>actor</b> action <key chip> <b>title</b>` with a
  small type glyph: primary @ for mentioned, teal user-plus for assigned), one-line
  clamped snippet, time top-right, hover actions (mark read / archive). Selected card:
  primary border. Contains **unread `mentioned` + `assigned` only**; once read they flow
  into the day feed. Never stacks.
- **Feed (V1 anatomy):** uppercase letter-spaced day header with trailing hairline
  (Today / Yesterday / Mon Jul 14…). Rows: unread primary dot (8px) column, tinted
  30px icon bubble per type (comment = gray message-square, status = gray swap-arrows),
  two-line body — line 1 sentence + optional "N updates" stack pill; line 2 = 2-line
  clamped snippet with left rule (comments) or sm `StatusBadge` from → to transition
  chips (status). Time right, hover actions right. Read rows dim (secondary ink, normal
  weight); unread bold names/titles.
- **Load more:** ghost row at feed end when a full page (limit) was returned; fetches
  with `before=<oldest created_at>`.
- **Empty states:** existing `EmptyState` block variant — inbox icon, "You're all caught
  up" (+ per-filter variants: e.g. no mentions); archived view its own empty state.

## 4. Right pane (desktop ≥768px)

- Existing `TaskDetail` rendered **inline** (not the drawer overlay) in a `flex:1` pane
  with left border. Selecting a notification: mark read → `openTask(task_id)` (reuses all
  loading: comments/subtasks/attachments/activity) → detail renders beside the list.
- `WorkOSApp` suppresses the drawer overlay when `view === 'inbox'` on desktop; mobile
  (<768px) keeps today's full-screen detail behavior, list is full-width.
- `TaskDetail` gains optional `highlightCommentId` prop: for `mentioned`/`commented`
  notifications (which carry `comment_id`), the Comments tab scrolls to and tints that
  comment (primary 7% background + 2px primary left rule, per mockup).
- Nothing selected → `EmptyState` quiet pane ("Select a notification").
- Task gone (deleted / visibility revoked → `GET /tasks/{id}` 404): pane shows
  `EmptyState` "Task no longer available"; the row remains mark-readable/archivable.

## 5. Backend

### 5.1 Schema

`workos_notification.archived` — `Boolean`, `NOT NULL`, server default `false`. One
Alembic migration on the current head. Archive implies read: `set_archived(..., True)`
also sets `read = true`.

### 5.2 Endpoints (all `require_workos`, intrinsically scoped to `user.id` — same posture
as mark-read; access doc §4 gets these rows)

| Route | Behavior |
|---|---|
| `POST /notifications/archive` | Body `{ids?: [...], all_read?: bool, archived: bool}`. `ids` → set `archived` on caller-owned rows only; `all_read: true` + `archived: true` → archive every read, non-archived row. Returns `{unread}` like mark-read. |
| `GET /notifications` | New `archived: bool = false` query param. Default excludes archived; `archived=true` returns only archived. `unread_only`/`limit≤200`/`before` unchanged. |
| `GET /notifications/counts` | `{unread, by_type: {mentioned, assigned, commented, status_changed}}` — unread AND non-archived only. |

### 5.3 DAO

`Notifications.set_archived(user_id, ids=None, all_read=False, archived=True)`,
`list_for_user(..., archived=False)`, `counts_for_user(user_id)`. `mark_read` unchanged.
Bootstrap `notifications_unread` unchanged (archived rows are read, so already excluded).

### 5.4 Realtime

No new events. Archive is user-local; the acting client updates its own store.
`workos:notification.created` keeps feeding live rows. Split-pane opens join the
notification's workstream room (`enterRoom(streamKey(data.workstream_id))`,
ref-counted, left again on `closeTask`) so the existing comment/activity/task
events stream into the pane even for tasks outside the current workstream;
`task.updated` / `task.deleted` also reconcile the `inboxTask` fallback (a
deleted task flips the pane to "Task no longer available").

## 6. Frontend architecture

```
views/InboxView.svelte          — split-pane container, header, controls, sections
views/inbox/NeedsYouCard.svelte — accent-inset card
views/inbox/FeedRow.svelte      — V1-anatomy feed row (incl. stack expand)
views/inbox/TypeGlyph.svelte    — tinted icon bubble / inline type glyph
lib/inbox.ts                    — pure grouping: groupInbox(list) → {needsYou, days};
                                  day bucketing, consecutive same-task stacking
```

Store (`lib/store.ts`):
- `notificationCounts` writable, set by `loadNotifications()` (list + `/counts` in
  parallel) and adjusted client-side on read/receive events.
- `archiveNotifications(ids, archived)` — optimistic removal/restore + server sync;
  `archiveAllRead()`.
- Archived list lazy-loads on first Archived-view open (separate store or param refetch).
- `openInboxNotification` (desktop split-pane): mark read + resolve the task + set
  `highlightCommentId` + join the task's workstream room (ref-counted); **no**
  `view.set('board')`. The old navigate-away `openNotification` remains for other
  surfaces (My Work rail) and for mobile inbox taps — and the InboxView unmount
  cleanup must not clear the selection on mobile, or that navigate-away open would
  close the task dialog before it renders.
- Realtime `notification.created`: prepend + bump `unread` and `by_type[type]`.

## 7. Out of scope

- New notification sources (due-soon/overdue reminders, digests) and per-type mute
  preferences (deferred "full overhaul" option).
- Cross-tab archive sync via realtime events.
- Keyboard j/k triage navigation (candidate follow-up).
- My Work rail restyle beyond what `summarizeNotification` already shares.

## 8. Testing & verification

- **Vitest:** `lib/inbox.ts` grouping (day buckets incl. Today/Yesterday boundaries,
  stacking merges consecutive same-task only, needs-you extraction = unread
  mentioned/assigned only); store tests — optimistic archive + rollback, counts
  decrement on read, realtime prepend + count bump, split-pane `inboxTask`
  reconcile on cross-workstream `task.updated` (extend `store.test.ts`).
- **Pytest:** archive endpoint scoping (cannot archive another user's rows), archive
  implies read, `all_read` sweep, `archived` list filter, counts correctness, limit
  clamp regression.
- **Static:** `svelte-check` clean; design-system greps (no `sky-500`, no bare
  `rounded`, `focus-visible` present on new interactive elements).
- **Browser smoke** (Docker container + Vite hot reload per runbook): seed
  notifications of all four types, verify needs-you vs feed split, stacking expand,
  tabs/toggle/archived flows, split-pane open + comment highlight, mobile width, dark
  mode, sidebar badge primary color.
