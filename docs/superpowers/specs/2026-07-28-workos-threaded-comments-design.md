# WorkOS Threaded Comments Redesign — Design Spec

**Date:** 2026-07-28
**Status:** Approved (brainstorm complete, all sections user-approved)
**Mockup:** `assets/2026-07-28-comments-mockup.html` (v2, user-approved)

## 1. Goal

Replace the flat, plain comment list in the task detail drawer with a modern threaded
comment experience: nested replies to unlimited depth, emoji reactions, a rich mention
composer (no raw `@[Name](mention:id)` tokens visible), image attachments with inline
previews, and list controls (count, sort, show-more). Visual language follows the
approved mockup: primary color `#003b4a`, thread rails, avatar-led cards.

## 2. Decisions (user-locked)

| Topic | Decision |
|---|---|
| Reactions | Emoji reactions, fixed 6-emoji allowlist: 👍 ❤️ 🎉 👀 😂 🚀. Counts + who reacted. Toggle semantics. No free-form picker. |
| Nesting UI | Indent cap at 3 levels with rail lines **plus** collapsible threads (`▾ N replies` toggle on any comment with children). Depth ≥ 4 renders at depth-3 indent with `↳ replying to @Name` chip. Data model depth unlimited. |
| Mention UX | Rich contenteditable composer with atomic mention chips + caret-anchored `@` typeahead. Same wire format as today. |
| Delete rule | Tombstone when comment has replies (placeholder "This comment was deleted", replies survive); hard delete when childless. |
| Reply notifications | New distinct `replied` notification type for the parent comment's author. |
| List controls | In-panel count header, sort dropdown (Most recent / Oldest first, top-level only), client-side show-more pagination (first 10 top-level). |
| Slicing | One spec, one plan, one migration; reactions are later tasks in the same plan. |
| Primary color | `#003b4a` for all comment-UI accents (chips, active reactions, focus ring, send button, collapse links, count pill). |
| Mention button | The old users-icon mention button is removed. `@` typeahead is the only mention entry point. |
| Comment attachments | Images only, thumbnail previews inside the comment body, click expands to lightbox. |

## 3. Data model & migration

### 3.1 `workos_comment` — two new columns

- `parent_id` (Text, nullable). `NULL` = top-level. Parent must be a comment on the
  **same task** (validated server-side). Chain gives unlimited depth.
- `deleted_at` (BigInteger, nullable). Tombstone marker. When set: `body` cleared to
  `''`, `mentions` cleared to `[]`, reactions purged.

### 3.2 New table `workos_comment_reaction`

```
id          Text PK
comment_id  Text
user_id     Text
emoji       Text        -- from allowlist: 👍 ❤️ 🎉 👀 😂 🚀
created_at  BigInteger
UNIQUE (comment_id, user_id, emoji)
```

Same user + same emoji again = remove (toggle). Allowlist enforced server-side.

### 3.3 Migration

One alembic revision, additive only, SQLite-safe (`batch_alter_table` for the
add-columns). Existing comments get `parent_id = NULL` → all top-level; nothing breaks.

### 3.4 `CommentModel` (pydantic)

Gains `parent_id: Optional[str]`, `deleted_at: Optional[int]`, and
`reactions: list` — aggregated as `{emoji, count, user_ids}` entries, grouped in
Python from one query per task fetch (per-task comment volume is small).

## 4. Backend API

| Route | Change |
|---|---|
| `POST /tasks/{id}/comments` | Accepts optional `parent_id`. Validation: parent exists (404), `parent.task_id == task_id` (400), parent not tombstoned (400). Existing guards (`require_workos` + `require_task_visible`) unchanged. |
| `PATCH /comments/{id}` | Unchanged capability (author-only, no admin bypass). New: editing a tombstoned comment → 400. |
| `DELETE /comments/{id}` | Unchanged capability (author OR team owner/admin). Behavior forks: has children → tombstone (set `deleted_at`, blank body/mentions, purge reactions); childless → hard delete as today. |
| `POST /comments/{id}/reactions` | **NEW.** Body `{emoji}`. Toggle add/remove. Guards: `require_workos` → fetch (404) → `require_task_visible` → emoji in allowlist (400) → not tombstoned (400). Any task-visible user may react; no capability entry needed. |
| `GET /tasks/{id}/comments` | Returns `parent_id`, `deleted_at`, aggregated `reactions` per comment. |
| `POST /tasks/{id}/attachments` | New rule: when `comment_id` is set, `content_type` must be `image/*` (400 otherwise), in addition to the existing `ATTACHMENT_MIME_ALLOW` check and the existing comment-belongs-to-task validation (G11). Task-level uploads (no `comment_id`) unchanged. |

Tombstone edge cases:
- A tombstone with all-deleted children never un-tombstones (accepted; Reddit/Slack behavior).
- Reply button hidden on tombstones client-side; server rejects anyway.
- Reactions rejected on tombstones.
- Comment images: attachment rows are untouched by tombstone or hard delete (same as
  today) — they remain task attachments visible in the Attachments panel and Files
  view; only the thumbnail row is hidden on a tombstoned comment.

## 5. Notifications

- New `replied` type registered in `WORKOS_RULES` notification toggles and
  `_notif_enabled`, visibility-gated through `can_see_workstream` exactly like
  existing types (see access-control doc §5, Channel B).
- Per-recipient precedence on comment create: **mentioned > replied > commented** —
  each recipient receives exactly one notification per comment event. The parent
  comment's author gets `replied` unless they were @mentioned in the reply. Self
  always excluded.
- Inbox: `replied` joins the needs-you bucket (like `mentioned`); `TypeGlyph`,
  `FeedRow`, and inbox lib updated.
- **Reactions notify nobody** — deliberate anti-noise decision.

## 6. Realtime

Existing workstream-room events (Channel A; gating untouched):

- Comment created/updated payloads carry `parent_id` / `deleted_at`.
- Tombstoning emits an **updated** event (not deleted) so clients swap in the
  placeholder live; hard delete emits deleted as today.
- **NEW** `comment_reaction` event: `{comment_id, reactions}` full aggregate —
  idempotent, no op-ordering issues.
- Comment-image upload emits the existing attachment event; clients re-render the
  thumbnail row.

The access-control reference doc must be updated in the same plan: new endpoint rows
in the Comments table, `replied` in the notification-type list, `comment_reaction`
event note in §5.

## 7. Frontend — rich mention composer

New `RichComposer.svelte`, used in three spots: main composer, inline reply composer
(compact variant), edit-in-place. Replaces the plain textarea.

- **Typeahead:** typing `@` opens a people popup anchored at the caret rect
  (fallback: anchored to the composer edge on mobile). Filters the team `directory`
  store as you type; ↑/↓/Enter keyboard nav; Esc closes the popup only.
- **Chips:** picking a person inserts a `contenteditable="false"` inline span styled
  as a `#003b4a` pill (`@Felwa`). Atomic: one backspace removes the whole chip; a
  broken half-token is impossible.
- **Serialization:** on send, walk child nodes → text nodes verbatim, chips →
  `@[Name](mention:ID)`. Wire format identical to today — backend `parse_mentions`,
  `mentions.ts`, and notification fan-out untouched. Edit mode deserializes tokens
  back into chips.
- **Paste:** plain text only (HTML stripped in the paste handler).
- **Keys:** Enter sends; Shift+Enter inserts newline; Esc in a reply/edit composer
  cancels it with `stopPropagation` so the drawer stays open (subtask-panel lesson).
- **Images:** attach button (image-labeled) accepts `image/*` only; selected images
  show as pending-preview chips with ✕ inside the composer. On send: create the
  comment first, then upload each image with the new comment's `comment_id`.
- The old users-icon mention button is removed.
- Body remains markdown; markdown rendering of comment bodies is unchanged.

**Mention rendering in comment bodies:** token → `[@Name](mention://id)` markdown
link; CSS styles `a[href^="mention://"]` as a `#003b4a` chip; click prevented
(no-op). Fallback if the Markdown component fights this: current bold rendering.

## 8. Frontend — thread UI

Per the approved mockup (`assets/2026-07-28-comments-mockup.html`):

- **Header:** "Comments" + `#003b4a` count pill + sort dropdown (Most recent /
  Oldest first). Sort applies to top-level comments only; replies are always
  chronological (ascending) inside a thread.
- **Comment card:** avatar (existing WorkOS initials/avatar colors), name + live
  relative time ("58 minutes ago"), markdown body with mention chips, thumbnail row
  for comment images, then the action row: reaction chips (viewer's own reaction =
  `#003b4a` outline + tint), 😊+ opens the 6-emoji picker popover, Reply, ⋯ menu
  (Edit / Delete under existing permission predicates).
- **Threading:** depth 1–3 indent with 2px rail lines; depth ≥ 4 stays at depth-3
  indent and shows a `↳ replying to @Name` chip.
- **Collapse:** every comment with children gets a `▾ N replies` toggle
  (`▸ N replies` when collapsed). Default expanded; collapsed state is
  session-local (not persisted).
- **Tombstone:** gray italic "This comment was deleted" placeholder; replies intact;
  no Reply button, no reactions.
- **Show more:** first 10 top-level comments render; the rest behind a "Show more"
  button (client-side slice — the full list is already fetched).
- **Reply composer:** compact `RichComposer` inline under the target comment,
  auto-focused; Esc cancels.
- **Lightbox:** clicking a thumbnail opens a full-size overlay; Esc / click-outside
  closes with `stopPropagation` so the drawer stays open.
- **Tree building:** client-side from the flat fetched list by `parent_id`
  (orphan-safe: an orphaned reply — parent hard-deleted before fetch — is promoted
  to top-level rather than dropped).
- **Dark mode:** all styling via existing token classes; same layout.
- **Mobile (<880px):** rails narrow to 12px indent; everything else identical.
- Comment images live in the same attachment table, so they also appear in the
  task Attachments panel and the workstream Files view (accepted).

## 9. Testing

**Backend (pytest, existing workos test pattern):**
- `parent_id` validation: wrong task → 400, missing parent → 404, reply to tombstone → 400.
- Delete fork: with children → tombstone (body blanked, mentions cleared, reactions purged); childless → hard delete.
- Reaction toggle: add/remove idempotence, allowlist reject, tombstone reject, unique constraint.
- Notification precedence: mentioned > replied > commented — one notification per recipient, self excluded, visibility gate held.
- Comment-attachment MIME: `comment_id` set + non-image → 400.
- GET returns `parent_id` / `deleted_at` / aggregated reactions.

**Frontend (vitest, existing store.test pattern):**
- Tree build from flat list, orphan promotion.
- Sort top-level asc/desc; replies always ascending.
- RichComposer serialization round-trip (chips ↔ tokens); paste strips HTML.
- Reaction aggregate merge from realtime event.
- Inbox `replied` row rendering.

**Browser smoke (end of plan, checklist):** post/reply 4 levels deep, collapse
toggle, react from a second account, live realtime both directions, tombstone
live-swap, mention typeahead keyboard-only, image upload → thumbnail → lightbox,
dark mode, mobile width, inbox `replied` row.

## 10. Out of scope

- Reaction notifications.
- Free-form emoji picker.
- Persisted collapse state.
- Server-side comment pagination (client-side slice only).
- Threaded comments anywhere outside the task detail drawer.
