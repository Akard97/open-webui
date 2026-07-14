# WorkOS — Files view (design)

> Approved 2026-07-14. Mockup: `docs/mockups/workos-files-v1.html` (v1, user-approved).
> Activates the existing dead **Files** tab in the workstream top bar.

## Goal

One place to see every file attached inside a workstream — task attachments and
comment attachments — with download and a link back to the owning task. Clean and
read-only: uploading stays on the task detail drawer.

## Scope

- **In:** workstream-scoped file listing, type filtering, search, sort, list/grid
  modes, recency grouping, image thumbnails, download, open-task, realtime refresh,
  dark mode, responsive.
- **Out:** upload from this view, delete from this view, per-file "More" menu,
  pagination UI (server caps at 1000 rows), file preview modal, team- or
  workspace-level file views.

## Backend

### DAO — `Attachments.list_for_workstream`

`backend/open_webui/models/workos.py`, on `AttachmentsDao`:

- Join `workos_attachment` × `workos_task` on `task_id`, filter
  `WorkosTask.workstream_id == workstream_id`.
- Order `created_at` DESC, `limit(1000)`.
- Returns enriched dicts (not bare `AttachmentModel`): all attachment fields plus
  `task_key`, `task_title`, `task_status` from the joined task row.

### Route — `GET /workstreams/{workstream_id}/attachments`

`backend/open_webui/routers/workos.py`, attachments section:

- Gates: `require_workos` → `require_workstream_visible` — byte-identical posture
  to `GET /workstreams/{id}/activity`. No new visibility surface: task visibility
  is derived 1:1 from workstream visibility (access-control reference §2), so
  every attachment under a visible workstream is visible.
- Response: `[{ id, task_id, comment_id, name, size, content_type, created_by_id,
  created_at, task_key, task_title, task_status }]`.
- Read-only; no writes, no notifications.

Uploader display names are **not** joined server-side — the frontend resolves
`created_by_id` against the directory store, same as comments do.

## Frontend

### Wiring

- `lib/store.ts`: `ViewKey` union gains `'files'`.
- `chrome/Topbar.svelte`: Files tab flips to `live: true` (tab row already renders
  on mobile, so no extra mobile nav work).
- `WorkOSApp.svelte`: `files` view renders `FilesView`; Topbar condition includes it.
- `lib/api.ts`: `listWorkstreamAttachments(workstreamId)`.

### Components (per approved mockup)

- `views/FilesView.svelte` — owns fetch + state (raw rows, type filter, query,
  sort, mode) and renders toolbar, groups, empty states.
- `views/files/FileRow.svelte` — list row: type tile or image thumb, name,
  "via comment" pill (when `comment_id` set), task chip with status dot, uploader
  avatar + name, date, size, hover actions (Download, Open task).
- `views/files/FileCard.svelte` — grid card: large preview (image thumb or tinted
  type glyph + extension pill), name, task key, size.
- Shared pure helpers in `views/files/lib.ts`: extension → type-group mapping
  (img / pdf / doc / sheet / other), byte formatting, recency-group bucketing
  (Today / This week / Earlier, local tz).

### Behavior

- Fetch on view activation and on workstream switch; loading state while pending.
- Toolbar: type chips with live counts (All / Images / PDFs / Docs / Sheets /
  Other), search (name substring), sort dropdown (Newest — default / Name / Size,
  shadcn `DropdownMenu`), segmented list ⇄ grid toggle. All client-side.
- List mode groups rows by recency using the List view's section style; grid mode
  is a flat gallery per group.
- Image thumbnails: `content_type.startsWith('image/')` → `attachmentUrl(id)` as
  `img src` (cookie-authed; pattern already live in `AttachmentList.svelte`).
- Download: `<a href={attachmentUrl(id)} target="_blank">` — existing pattern.
- Open task: opens the task detail drawer via the store's task-open path.
- Empty states via `ui/EmptyState.svelte`: no files at all ("No files yet — attach
  files from any task") vs. no filter/search match.
- Responsive per mockup: columns collapse under 1280/860px, task key moves under
  the filename, actions always visible on touch widths.

### Realtime

`workos:attachment.created` / `workos:attachment.deleted` already broadcast to the
workstream room, which the client already joins (ref-counted rooms). While the
Files view is active, either event for the current workstream triggers a refetch.
No store surgery, no new rooms.

## Testing

- **Backend (pytest):** endpoint returns joined rows across multiple tasks;
  includes comment attachments; ordering + cap; non-member → 404; restricted
  workspace non-member → 404 (member + app-admin → 200); unknown workstream → 404.
- **Frontend (vitest):** `views/files/lib.ts` helpers — type-group mapping, byte
  formatting, recency bucketing edge cases (today boundary, week boundary).
- **Manual browser smoke** (after build): tab activation, chips/search/sort/toggle,
  thumbnail auth, download, open-task, realtime refetch on upload/delete from the
  task drawer, dark mode, phone width.
