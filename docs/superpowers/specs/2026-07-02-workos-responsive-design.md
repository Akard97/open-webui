# WorkOS Responsive / Mobile Design

**Date:** 2026-07-02
**Status:** Approved (shell, views, task detail, dialogs — all four sections approved by user)

> **Amendment 2026-07-03 (post-smoke, user-directed):** the bottom tab bar is gone.
> Mobile navigation now mirrors the chat tool's pattern: the global Osool app bar sits on
> top, and a WorkOS header row (`chrome/MobileHeader.svelte` — drawer toggle w/ unread dot
> + breadcrumb title) sits under it; the toggle opens the nav drawer. My Work and Inbox
> moved into the drawer above the team switcher (mirroring the desktop sidebar panel).
> `BottomNav.svelte` deleted; the Topbar title row is desktop-only (mobile header carries
> the title). §1's "bottom tab bar + safe-area" text below is superseded by this.
**Goal:** WorkOS fully usable on phones. Today the shell renders a fixed ~312px sidebar (56px icon rail + 256px tree panel) inside a horizontal flex root, leaving ~63px of content on a 375px phone. Views have almost no breakpoints (15 total across 7 files).

## Decisions (from brainstorming)

| Question | Decision |
| --- | --- |
| Support level | Fully usable on phone (not just readable) |
| Mobile navigation | Bottom tab bar + workstream-tree drawer |
| Dense views | Native adaptation per view (board swipe, list cards, calendar agenda) |
| Task detail | Full-screen takeover below `md` |
| Implementation approach | **B:** reuse OWUI global `mobile` store (`window.innerWidth < 768`, maintained in `src/routes/+layout.svelte`) for structural swaps; plain Tailwind breakpoint classes for cosmetic stacking |

Desktop (≥768px) behavior is unchanged throughout.

## §1 Shell

**Files:** `WorkOSApp.svelte`, `chrome/Sidebar.svelte`, new `chrome/BottomNav.svelte`, new `chrome/NavDrawer.svelte`, new `chrome/WorkstreamTree.svelte`.

- `WorkOSApp.svelte`: `{#if !$mobile}<Sidebar />{/if}`; root becomes a column on mobile with content area + `<BottomNav />` at the bottom.
- **BottomNav** (mobile only): three tabs — My Work (`view = 'mywork'`), Inbox (`view = 'inbox'`, unread dot from `unreadCount`), Browse (opens NavDrawer). Active state follows `$view` (workstream views highlight Browse). Safe-area padding: `pb-[env(safe-area-inset-bottom)]`.
- **NavDrawer** (mobile only): left slide-in overlay (~82vw) over a scrim. Contains: team switcher header (same behavior as sidebar panel header), `WorkstreamTree`, footer with admin gear (`canUseAdmin` gated → `view = 'admin'`), `ThemeSwitcher`, close button. Selecting a workstream sets it current, sets view to last-used tab (existing store behavior), closes drawer. Scrim tap and Escape close. If viewport crosses ≥768px while open, force-close.
- **WorkstreamTree extraction:** the teams → workspaces → workstreams tree (expand state, kebab/context menus, "Add a user…" affordances) moves out of `Sidebar.svelte` into `chrome/WorkstreamTree.svelte`; desktop Sidebar panel and mobile NavDrawer both render it. No behavior change on desktop — pure extraction. Context-menu (right-click) paths are desktop-only by nature; the existing kebab menus cover mobile.
- **Topbar** mobile: single row — truncated `workspace · workstream` title; decorative avatar stack, Share, and Automation buttons hidden (`hidden md:flex`). Tab row becomes a horizontally scrollable, snap-free pill row (scrollbar hidden). No hamburger — navigation lives in BottomNav.

## §2 Views

- **BoardView:** columns `w-72 flex-none` → mobile `w-[82vw] flex-none snap-center`; scroller gets `snap-x snap-mandatory`. CSS-only (Tailwind `max-md:` variants); no store branch. Drag-and-drop stays as-is (touch DnD not a Phase goal; status changes available via task detail).
- **ListView:** below `md`, replace the grid-row table with tappable cards inside the existing group sections: title + key, status dot, due date, priority flag, assignee avatars. Tap opens task detail. Inline cell editing (status/assignee/date/priority dropdowns in rows) is desktop-only; mobile edits happen in the task detail. Implemented as an `{#if $mobile}` branch inside ListView reusing group data.
- **CalendarView:** below `md`, render an agenda instead of the `grid-cols-7` month grid: month header with prev/next, then day-grouped task chips for the visible month (reuses existing `calendar.ts` month data — pure helpers for agenda grouping added there with vitest tests). "Unscheduled" rail becomes a collapsible section above the agenda. Month grid and drag-to-schedule are desktop-only.
- **OverviewView / MyWorkView:** already stack via `grid-cols-1 xl:` / `lg:` — audit paddings (`px-` scales down), KPI bands stay 2-col at base, hero/donut sizes clamp. Cosmetic breakpoints only.
- **InboxView:** spacing/width audit only.
- **Admin (AdminApp + tabs):** "don't break" tier — tables wrapped in `overflow-x-auto`, forms stack. Desktop remains the primary admin surface.
- **FilterBar:** search input becomes its own full-width row; filter/sort chips sit in a horizontally scrollable row below.

## §3 Task detail

**File:** `views/TaskDetail.svelte` (+ `detail/*` children as needed).

Below `md`, the shadcn Dialog content becomes a full-screen takeover: `inset-0 w-screen h-dvh max-w-none max-h-none rounded-none`. Header: back arrow (closes → clears `selectedTask`), task key, kebab. Title + status/priority pills below. The properties grid (assignees, dates, progress, tags) collapses into a single "Details" accordion above the tabs (collapsed by default). Tabs (Comments / Subtasks / Activity) unchanged. Comment composer pinned to the bottom with `pb-[env(safe-area-inset-bottom)]`; relies on browser visual-viewport behavior for the keyboard. Desktop dialog is untouched.

## §4 Dialogs

`ModalHost` modals, `TeamSettingsDialog`, `WorkspaceSettingsDialog`, `RestrictConfirmDialog`: below `md`, cap at `w-[95vw] max-h-[90dvh]` with internal scrolling; two-column internal grids stack to one column. Cosmetic breakpoints only — no behavior change.

## Non-goals

- Touch drag-and-drop for board/calendar (edit via task detail instead).
- Timeline/Gantt, saved views (deferred per Phase 3a).
- Backend/API changes — none anywhere in this work.
- PWA/native wrapper concerns.

## Error handling / edge cases

- Resize across the 768px boundary: NavDrawer and any mobile-only overlays force-close; `$mobile` flips structure reactively (Svelte re-render — component state like drawer-open lives in stores/local state that resets safely).
- `$view === 'admin'` on mobile: reachable from drawer footer; Admin renders in don't-break mode.
- Realtime events unaffected — store layer untouched.

## Testing

- Vitest: new pure helpers (agenda grouping in `calendar.ts`), any extracted tree helpers. Existing suites must stay green.
- Manual smoke on the user's own Vite hot-reload server (do not start a dev server unprompted) at 375px and 768px: shell nav, all views, task detail, dialogs, dark mode.
