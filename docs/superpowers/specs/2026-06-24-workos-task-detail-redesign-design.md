# WorkOS Task Detail Panel Redesign

**Date:** 2026-06-24
**Branch base:** `osool`
**Status:** Approved design — ready for implementation plan

## Goal

Restyle the right-side task detail drawer to match the provided reference image
(a clean, read-first task panel), using shadcn-svelte primitives and the Osool
**teal** accent in place of the image's indigo/purple. All store logic and
backend actions are reused unchanged — this is a presentation + interaction
redesign, not new backend behavior.

The reference image's subtasks section is **out of scope**: it is rendered as a
placeholder empty state to be filled in later.

## Context

- Current panel: `src/lib/components/workos/views/TaskDetail.svelte` — a 460px
  right drawer with an overlay. It is edit-first: always-visible `<select>`s for
  status/priority/assignee, a native date input, a progress `<input type=range>`,
  inline label toggles, a description editor, `AttachmentList`, and a combined
  comment+activity `Feed`.
- shadcn-svelte is installed and scoped to `.workos-root` (see `src/tailwind.css`,
  the `.workos-root` radius + border rules). Installed primitives:
  `avatar`, `badge`, `button`, `card`, `checkbox`, `dialog`, `dropdown-menu`,
  `input`, `label`, `scroll-area`, `select`, `separator`, `spinner`, `tabs`,
  `tooltip` (under `src/lib/components/ui/`).
- The repo's shadcn `--primary` token is neutral gray; the established WorkOS
  accent is **teal** (`teal-600` light / `teal-400` dark), used across existing
  WorkOS components.
- Data model (`src/lib/components/workos/lib/types.ts`): a `Task` has a **single**
  `assignee_id`, plus `status`, `priority`, `due_date`, `progress`, `labels`,
  `description`. There is no avatar image URL — only display names (directory),
  so avatars use initials fallbacks.

## Decisions (from brainstorming)

1. **Editing model:** Read-first with click-to-edit. Fields render as clean
   display rows; interacting reveals an inline editor/popover/select.
2. **Components:** Build with shadcn-svelte primitives (Avatar, Tabs, Badge,
   Card, Button, DropdownMenu, Select). The rest of WorkOS stays hand-rolled;
   this panel is the first real shadcn consumer.
3. **Priority & Progress:** Keep dedicated property rows (the image omits them,
   but we don't want to lose edit capability).
4. **Header actions:** Map the image's icon cluster to real actions — pencil
   focuses the title for editing; share **copies the task link to clipboard**;
   `…` opens a DropdownMenu containing **Delete** (gated by `canDeleteTask`).
   Close (✕) replaces the image's top-left expand glyph.
5. **Tabs:** Split today's combined feed into separate **Comments** and
   **Activities** tabs, plus a **Subtasks** placeholder tab — matching the image.
   `Feed.svelte` is removed (superseded).

## Layout (top → bottom)

1. **Header bar** — left: close (✕) then breadcrumb `{workstream name} / {status
   label}`. Right: action cluster — pencil (focus title), share (copy task link),
   `…` DropdownMenu (Delete, gated).
2. **Title** — large/bold; renders as text, becomes an input on click or via the
   pencil. Commits on change via `editTask(id, { title })`.
3. **Property rows** — reusable `PropertyRow` (icon + label + value slot),
   read-first with click-to-edit:
   - **Status** — `StatusDot` + `STATUS_LABEL[status]` → DropdownMenu/Select to
     change. Includes `canceled`.
   - **Priority** — flag icon + priority pill (`Pills`) → Select (incl. "No
     priority").
   - **Due date** — calendar icon + formatted date (e.g. `5 March 2024`, or
     "Add due date" when empty) → reveals a date input.
   - **Assignee** — `Avatar` with initials fallback + display name (or
     "Unassigned") → Select of directory users.
   - **Tags** — label `Badge`s + an "add" affordance toggling labels via
     DropdownMenu (reuses existing `toggleLabel`).
   - **Progress** — a thin progress bar + `{progress}%` → reveals the slider.
   - **Description** — doc icon + "Description" label, then a bordered `Card`
     with the text (or "Add a description…") → click to edit (textarea + Save/
     Cancel; existing `descDraft`/`editingDesc` logic preserved).
4. **Attachments** — `AttachmentsPanel.svelte`: header "Attachment (N)" +
   **Download All** link (teal, right). File chips as `Card`s (file-type icon +
   name + size + Download link to `attachmentUrl(id)`), plus a `+` add card that
   triggers file upload (`uploadFiles`). Delete affordance gated by
   `canDeleteAttachment` (preserved from `AttachmentList`). "Download All"
   triggers a download per file. Shows only non-comment attachments
   (`!a.comment_id`).
5. **Tabs** (shadcn `Tabs`) — **Subtasks** | **Comments (N)** | **Activities**:
   - *Subtasks* → `SubtasksPlaceholder.svelte` empty state ("Subtasks coming
     soon" + muted illustration/text).
   - *Comments* → `CommentItem` list + `CommentComposer` (both reused). Count
     badge = `comments.length`.
   - *Activities* → `ActivityItem` list only (derived from `activity` store).

## Component / file structure

**Rewrite**
- `views/TaskDetail.svelte` — drawer shell (overlay + 460px panel), `ScrollArea`,
  header, title, property rows, attachments, tabs. Composes the new pieces.

**New** (`views/detail/`)
- `DetailHeader.svelte` — breadcrumb + action cluster + close. Props: task.
- `PropertyRow.svelte` — presentational shell: `icon` name, `label`, default slot
  for the value/editor. Keeps each row visually consistent.
- `AssigneeField.svelte` — Avatar (initials) + name display + assignee Select.
- `AttachmentsPanel.svelte` — the attachment card grid + Download All + add.
- `SubtasksPlaceholder.svelte` — empty-state placeholder.

**Reused unchanged**
- `CommentItem`, `CommentComposer`, `ActivityItem`, `Pills`, `StatusDot`, `Icon`,
  `lib/store`, `lib/types`, `lib/roles`, `lib/api`.

**Removed**
- `views/detail/Feed.svelte` — superseded by the Comments/Activities tabs.

Status/priority/due-date/labels/progress editors stay inline in `TaskDetail`
wrapped in `PropertyRow` (using shadcn DropdownMenu/Select + native date/range
inputs) to avoid over-fragmenting into one-line components.

## Color & theming

Use shadcn primitives for structure; apply **teal** explicitly for accents
(active tab underline/indicator, links such as Download/Download All, focus
rings, avatar fallback tint). Status/priority/label semantic colors are
unchanged (`Pills`, `StatusDot`). Dark mode preserved throughout
(`dark:` variants, `.workos-root` already themed).

## Behavior / data notes

- Breadcrumb status label uses `STATUS_LABEL`; workstream name from
  `currentWorkstream`.
- Date formatting: `Intl.DateTimeFormat` (e.g. `d LLLL yyyy` → "5 March 2024").
- Copy link: `navigator.clipboard.writeText(window.location.href)` (or a task
  deep-link if one exists; otherwise current URL). Briefly reflect "Copied".
- Comments tab count: `comments.length`. Activities tab: `activity` store items.
- No new store functions required; everything maps to existing exports
  (`editTask`, `removeTask`, `toggleLabel` logic, `uploadFiles`,
  `removeAttachment`, `attachmentUrl`).

## Testing & verification

- Logic is unchanged (reuses store actions), so the risk is visual/regression.
- The existing frontend test suite must stay green (`npm run test:frontend` or
  the project's vitest command). If any test references `Feed.svelte` or the old
  panel markup, update it to the new structure.
- Add light unit coverage only where genuinely new logic appears: the
  comments-vs-activities split selection and "Download All" iteration (if
  factored into a testable helper). Avoid testing pure markup.
- Browser smoke via the dev preview: open a task → screenshot each tab
  (Subtasks placeholder, Comments, Activities), edit a field (status/assignee/
  due date/description), verify dark mode, verify Download All + add attachment.

## Out of scope

- Real subtasks (data model, CRUD, progress donut) — placeholder only.
- Multiple assignees / invite flow (model is single-assignee).
- Any backend/API changes.
