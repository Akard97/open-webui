# WorkOS — URL Sync (Deep Linking) Design

> Approved 2026-07-19. Adds shareable URLs and refresh persistence to WorkOS via
> query-param sync ("Option A"). Path-based nested routes (Option B) were
> considered and deferred; this design does not foreclose them.

## Problem

WorkOS is a SPA mounted at a single SvelteKit route
([+page.svelte](../../../src/routes/(app)/workos/+page.svelte) →
[WorkOSApp.svelte](../../../src/lib/components/workos/WorkOSApp.svelte)). All
navigation lives in four Svelte stores in
[store.ts](../../../src/lib/components/workos/lib/store.ts): `view`,
`currentTeamId`, `currentWorkstreamId`, `selectedTaskId`. Nothing touches the
URL, so:

- No shareable links to a workstream or task.
- Refresh drops the user back to My Work (only `currentTeamId` survives, via
  localStorage).
- Browser Back exits WorkOS entirely.

Deep-linking was deliberately deferred out of Phase 3a; this is that slice.

## Decisions (locked with user)

1. **History behavior: pushState on major nav.** Switching view or workstream
   pushes a history entry; opening/closing the task drawer only replaces the
   URL (no entry). Back walks between views/workstreams and eventually exits
   WorkOS. Drawer closes via X/Esc as today, not via Back.
2. **URL scope: nav state only.** Filters and search text stay in-memory.
   Serializing them is a possible later slice; nothing in this design blocks
   it.

## 1. URL scheme

`/workos?view=<key>&ws=<id>&task=<id>`

| State store | Param | Rules |
|---|---|---|
| `view` | `view` | Omitted when `mywork` (the default view). Valid values: the 9 `ViewKey`s (`board`, `list`, `calendar`, `overview`, `timeline`, `files`, `mywork`, `inbox`, `admin`). |
| `currentWorkstreamId` | `ws` | Present only for workstream views (`board`/`list`/`calendar`/`overview`/`timeline`/`files`). Global views (`mywork`/`inbox`/`admin`) never carry `ws`. |
| `selectedTaskId` | `task` | Present whenever the task drawer is open, in any view. |
| `currentTeamId` | — | **No param.** Derived from `ws` (workstream → workspace → `team_id`, all client-side from bootstrap). Global views keep today's localStorage team. |

Task **IDs**, not task keys — keys would need a resolution lookup; IDs work
directly against `GET /tasks/{id}`.

Examples:

- `/workos` → My Work
- `/workos?view=board&ws=abc123` → board for workstream `abc123`
- `/workos?view=board&ws=abc123&task=t42` → same board with the task drawer open
- `/workos?view=inbox` → inbox

## 2. Architecture

**One new module:** `src/lib/components/workos/lib/urlSync.ts`. It is the only
place that knows URLs exist. Views, sidebar, and dialogs keep calling
`selectWorkstream` / `openTask` / `view.set` exactly as today — zero changes to
call sites.

Two one-way flows with a guard flag between them:

### Stores → URL (write)

Subscribe to `view` + `currentWorkstreamId` + `selectedTaskId`; compute the
canonical query string per §1.

- `view` or `ws` changed → `pushState` (new history entry).
- Only `task` changed → `replaceState` (no entry).
- Writes are coalesced to a microtask so a compound transition
  (`selectWorkstream` sets `ws` *and* clears `task`) produces **one** history
  entry, not two.

Uses SvelteKit shallow routing (`pushState` / `replaceState` from
`$app/navigation`; SvelteKit 2.5 + Svelte 5 already in the repo).

### URL → stores (read)

Two triggers:

1. **Initial hydrate** — exactly once, after `loadBootstrap()` resolves (the
   bootstrap tree is required to validate `ws` and resolve the team).
2. **popstate** (Back/Forward) — subscription on the SvelteKit page URL;
   re-hydrate stores from params.

### Loop guard

An `applying` flag is set while URL→store hydration runs so the store
subscriptions do not echo a `pushState` back. Store→URL writes are skipped
while the flag is up.

### Wiring

`WorkOSApp.svelte` gains two lines: `initUrlSync()` after `loadBootstrap()` in
`onMount`, `destroyUrlSync()` in `onDestroy` (unsubscribes everything —
re-entering WorkOS must not double-subscribe).

## 3. Hydrate & error handling

Hydrate order (bootstrap data is already client-side; only tasks need
fetching):

1. Read params. Validate `view` against the `ViewKey` list — invalid → treat
   as absent (`mywork`).
2. `ws` present → look up in bootstrap `workstreams`.
   - **Found** → resolve team via its workspace, `currentTeamId.set(teamId)`,
     then `await selectWorkstream(ws)`.
   - **Not found** (deleted, no access — bootstrap is server-trimmed — or
     garbage) → toast "Workstream not available", strip `ws`+`task` params
     (replaceState), fall back to My Work. **No blank screens.**
3. `task` present → after the workstream's tasks load:
   - id in the loaded list → `openTask(id)`.
   - not in list → fetch `GET /tasks/{id}` directly (same fallback pattern as
     the inbox split-pane `inboxTask`): 200 → open; 404 → toast "Task not
     available", strip `task` param, stay on the view.
4. `task` without `ws` (e.g. a My Work deep link) → same direct-fetch path as
   3b.

### Access control posture

Per the access reference
([2026-06-26-workos-access-control.md](2026-06-26-workos-access-control.md)):
all `require_*_visible` gates return **404** for both "missing" and "not
yours", so deep links cannot distinguish existence from access — one error
path client-side, no information leak. The frontend remains a pure consumer;
this feature adds **no** new frontend access logic.

The existing admin-view guard in `WorkOSApp.svelte`
(`$view === 'admin' && !canUseAdmin($user)` → snap to board) already covers a
non-admin pasting `?view=admin`; the snap propagates back into the URL through
the write flow. No new code.

### Realtime safety

Hydration and popstate navigation go through the **existing**
`selectWorkstream` / `openTask` functions, so ref-counted room join/leave and
the "user moved on" guards in store.ts apply unchanged. A popstate navigation
is indistinguishable from a sidebar click below the urlSync layer.

### Bootstrap default-selection interplay

`loadBootstrap()` today auto-selects the first workstream of the current team
when none is set. When the URL carries a valid `ws`, that default selection is
redundant work (double task fetch + room join/leave churn). Rule: when the
initial URL contains a `ws` param, the bootstrap default-select is skipped and
hydration performs the only `selectWorkstream` call. (Implementation may pass
a flag into `loadBootstrap` or check the URL there; either is fine — behavior
is what's pinned: exactly one workstream selection on a deep-linked load.)

### Team conflict rule

URL wins when `ws` is present (link sharing is the point); localStorage
(`workos:current-team`) wins otherwise. A deep link into team B while
localStorage says team A switches the client to team B; localStorage updates
via the existing `currentTeamId` subscription.

## 4. Testing

- **`urlSync.test.ts`** (vitest, colocated like the other lib tests):
  - param serialization round-trip (stores → query string → stores)
  - `view` validation (bad value → mywork)
  - push-vs-replace decision table (view change, ws change, task-only change,
    compound ws+task transition = one entry)
  - loop guard: URL→store application does not trigger a store→URL write
  - hydrate fallback matrix: bad `ws` / bad `task` / bad `view` /
    `task` without `ws`
- **`store.test.ts`** untouched — store functions are not modified; the
  existing suite is the regression net.
- **Manual smoke checklist:**
  1. Copy board URL → open in new tab → same board, same workstream.
  2. Open task, copy URL → new tab → board + drawer open on that task.
  3. Refresh mid-board → same place.
  4. Back walks: board ws-A → list ws-A → board ws-B → Back → list ws-A →
     Back → board ws-A → Back → exits WorkOS.
  5. Open/close task drawer repeatedly → Back still exits in one step per
     major nav (no drawer entries).
  6. Paste URL with deleted task id → toast, view survives.
  7. Non-admin pastes `?view=admin` → lands on board.

## Out of scope (explicit)

- Filters/search in the URL (possible later slice; design doesn't block it).
- Task-key-based URLs (`OSL-123`).
- Path-based nested routes (Option B).
- Inbox notification deep links (`?view=inbox&notification=…`).
