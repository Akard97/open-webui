# WorkOS URL Sync (Deep Linking) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sync WorkOS navigation state (view / workstream / task) into `/workos?view=…&ws=…&task=…` query params so links are shareable, refresh keeps your place, and Back walks major navigation.

**Architecture:** One new pure module (`urlState.ts`: serialize/parse/history-op decision) + one new wiring module (`urlSync.ts`: store subscriptions → `pushState`/`replaceState`; page-store subscription → store hydration, with a loop-guard flag). Two small additive changes to `store.ts` (`loadBootstrap` option, `openTaskById`). `WorkOSApp.svelte` gains init/destroy calls. **No other call site changes** — views/sidebar keep calling `selectWorkstream`/`openTask`/`view.set` as today.

**Tech Stack:** SvelteKit 2.5 shallow routing (`pushState`/`replaceState` from `$app/navigation`), Svelte stores, vitest 1.6 (node environment — no jsdom installed, tests must not touch `window`/`document`).

**Spec:** `docs/superpowers/specs/2026-07-19-workos-url-sync-design.md` — read it before starting any task.

## Global Constraints

- URL scheme: `view` omitted when `mywork`; `ws` only for workstream views (`board`,`list`,`calendar`,`overview`,`timeline`,`files`); `task` whenever the drawer is open. No `team` param — derived from `ws`.
- History: `pushState` when view or ws changes; `replaceState` when only task changes; compound transitions (ws change + task clear) produce **one** entry.
- All hydration goes through the **existing** store functions (`selectTeam`, `selectWorkstream`, `openTask`, `closeTask`) so realtime room ref-counting and "user moved on" guards apply unchanged.
- Fallbacks never blank the screen: bad `ws` → toast "Workstream not available" + My Work; bad `task` → toast "Task not available" + param dropped.
- Exactly one workstream selection on a deep-linked load (bootstrap default-select skipped when URL has `ws`).
- No new frontend access logic — backend 404s uniformly for missing-vs-forbidden.
- Tests: `npm run test:frontend` (vitest, **node** env). Static check: `npm run check`.
- Commit per task, on the current branch (`osool`). Frontend is served by the user's own Vite hot-reload server — do NOT start a dev server, do NOT rebuild Docker.
- Code style: tabs, single quotes, `./`-relative imports inside `lib/`, comment density like `store.ts` (explain *why*, not *what*).

---

### Task 1: Pure URL state module (`urlState.ts`)

**Files:**
- Create: `src/lib/components/workos/lib/urlState.ts`
- Test: `src/lib/components/workos/lib/urlState.test.ts`

**Interfaces:**
- Consumes: `ViewKey` type from `./store` (type-only import — no runtime dependency, so tests need no mocks).
- Produces (used by Task 3):
  - `type NavState = { view: ViewKey; ws: string | null; task: string | null }`
  - `const WORKSTREAM_VIEWS: ReadonlySet<ViewKey>`
  - `buildQuery(state: NavState): string` — `''` or `'?view=…&ws=…&task=…'` (fixed param order)
  - `parseQuery(params: URLSearchParams): NavState`
  - `decideOp(prev: NavState, next: NavState): 'push' | 'replace' | 'none'`

- [ ] **Step 1: Write the failing test**

Create `src/lib/components/workos/lib/urlState.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { buildQuery, parseQuery, decideOp, WORKSTREAM_VIEWS, type NavState } from './urlState';

const st = (over: Partial<NavState> = {}): NavState => ({
	view: 'mywork', ws: null, task: null, ...over
});

describe('buildQuery', () => {
	it('empty for the default view with nothing open', () => {
		expect(buildQuery(st())).toBe('');
	});
	it('omits view=mywork but keeps task', () => {
		expect(buildQuery(st({ task: 't1' }))).toBe('?task=t1');
	});
	it('serializes view + ws + task in fixed order', () => {
		expect(buildQuery(st({ view: 'board', ws: 'w1', task: 't1' }))).toBe('?view=board&ws=w1&task=t1');
	});
	it('drops ws for global views even when a workstream is selected', () => {
		expect(buildQuery(st({ view: 'inbox', ws: 'w1' }))).toBe('?view=inbox');
		expect(buildQuery(st({ view: 'mywork', ws: 'w1' }))).toBe('');
	});
	it('workstream views carry ws', () => {
		for (const v of WORKSTREAM_VIEWS) {
			expect(buildQuery(st({ view: v, ws: 'w1' }))).toBe(`?view=${v}&ws=w1`);
		}
	});
});

describe('parseQuery', () => {
	const parse = (s: string) => parseQuery(new URLSearchParams(s));
	it('empty → mywork', () => {
		expect(parse('')).toEqual(st());
	});
	it('round-trips a full board state', () => {
		expect(parse('view=board&ws=w1&task=t1')).toEqual(st({ view: 'board', ws: 'w1', task: 't1' }));
	});
	it('unknown view → mywork, ws dropped', () => {
		expect(parse('view=bogus')).toEqual(st());
	});
	it('bare ws with no view implies board', () => {
		expect(parse('ws=w1')).toEqual(st({ view: 'board', ws: 'w1' }));
	});
	it('unknown view with ws also implies board (ws wins over garbage)', () => {
		expect(parse('view=bogus&ws=w1')).toEqual(st({ view: 'board', ws: 'w1' }));
	});
	it('global view ignores a stray ws param', () => {
		expect(parse('view=inbox&ws=w1')).toEqual(st({ view: 'inbox' }));
	});
	it('task survives on any view', () => {
		expect(parse('task=t9')).toEqual(st({ task: 't9' }));
		expect(parse('view=inbox&task=t9')).toEqual(st({ view: 'inbox', task: 't9' }));
	});
});

describe('decideOp', () => {
	it('view change → push', () => {
		expect(decideOp(st(), st({ view: 'inbox' }))).toBe('push');
	});
	it('ws change → push (even with a task change riding along)', () => {
		expect(decideOp(st({ view: 'board', ws: 'w1', task: 't1' }), st({ view: 'board', ws: 'w2' }))).toBe('push');
	});
	it('task-only change → replace (open and close)', () => {
		expect(decideOp(st({ view: 'board', ws: 'w1' }), st({ view: 'board', ws: 'w1', task: 't1' }))).toBe('replace');
		expect(decideOp(st({ view: 'board', ws: 'w1', task: 't1' }), st({ view: 'board', ws: 'w1' }))).toBe('replace');
	});
	it('no change → none', () => {
		const a = st({ view: 'list', ws: 'w1', task: 't1' });
		expect(decideOp(a, { ...a })).toBe('none');
	});
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/lib/components/workos/lib/urlState.test.ts`
Expected: FAIL — `Cannot find module './urlState'` (or equivalent resolve error).

- [ ] **Step 3: Write the implementation**

Create `src/lib/components/workos/lib/urlState.ts`:

```ts
// Pure URL <-> nav-state mapping for WorkOS deep linking. No store, DOM, or
// SvelteKit dependencies (ViewKey is a type-only import) — the wiring that
// actually reads/writes the address bar lives in urlSync.ts.
import type { ViewKey } from './store';

export type NavState = { view: ViewKey; ws: string | null; task: string | null };

// Views that render a specific workstream; global views (mywork/inbox/admin)
// never carry a `ws` param.
export const WORKSTREAM_VIEWS: ReadonlySet<ViewKey> = new Set<ViewKey>([
	'board', 'list', 'calendar', 'overview', 'timeline', 'files'
]);

const ALL_VIEWS: ReadonlySet<string> = new Set<string>([
	'board', 'list', 'calendar', 'overview', 'timeline', 'files', 'mywork', 'inbox', 'admin'
]);

/**
 * Canonical query string ('' or '?…') for a nav state. Param order is fixed
 * (view, ws, task) so plain string equality detects self-written URLs.
 */
export function buildQuery(state: NavState): string {
	const p = new URLSearchParams();
	if (state.view !== 'mywork') p.set('view', state.view);
	if (state.ws && WORKSTREAM_VIEWS.has(state.view)) p.set('ws', state.ws);
	if (state.task) p.set('task', state.task);
	const s = p.toString();
	return s ? `?${s}` : '';
}

/**
 * Parse URL params into a nav state. Lenient on hand-edited URLs: an unknown
 * view falls back to 'mywork', except that a `ws` param with a missing/bad
 * view implies 'board' (the natural home of a workstream link).
 */
export function parseQuery(params: URLSearchParams): NavState {
	const raw = params.get('view');
	let view: ViewKey;
	if (raw && ALL_VIEWS.has(raw)) view = raw as ViewKey;
	else if (params.get('ws')) view = 'board';
	else view = 'mywork';
	const ws = WORKSTREAM_VIEWS.has(view) ? params.get('ws') : null;
	return { view, ws, task: params.get('task') };
}

/**
 * History op for a state transition: view/workstream changes deserve a new
 * entry (Back walks them), task-drawer changes only rewrite the current one
 * (Back never merely closes the drawer).
 */
export function decideOp(prev: NavState, next: NavState): 'push' | 'replace' | 'none' {
	if (prev.view !== next.view || prev.ws !== next.ws) return 'push';
	if (prev.task !== next.task) return 'replace';
	return 'none';
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/lib/components/workos/lib/urlState.test.ts`
Expected: PASS — all tests green.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/urlState.ts src/lib/components/workos/lib/urlState.test.ts
git commit -m "feat(workos): pure URL<->nav-state mapping for deep linking"
```

---

### Task 2: Store additions — `loadBootstrap` option + `openTaskById`

**Files:**
- Modify: `src/lib/components/workos/lib/store.ts` (two spots: `loadBootstrap` ~line 211, new function after `openInboxNotification` ~line 706)
- Test: `src/lib/components/workos/lib/store.test.ts` (append a describe block)

**Interfaces:**
- Consumes: existing store internals (`tasks`, `myTasks`, `inboxTask`, `selectedTaskId`, `inboxRoomKey`, `streamKey`, `enterRoom`/`leaveRoom`, `loadTaskDetail`, `api.getTask`, `openTask`).
- Produces (used by Task 3 and Task 4):
  - `loadBootstrap(opts?: { selectDefaultWorkstream?: boolean }): Promise<void>` — default `true` preserves today's behavior; existing zero-arg callers unaffected.
  - `openTaskById(id: string): Promise<boolean>` — opens a task that may live outside the loaded lists; `false` means gone/unreadable (caller toasts + strips the param).

Both changes are **additive**; no existing store function's behavior changes when called as before. The existing `store.test.ts` suite is the regression net.

- [ ] **Step 1: Write the failing tests**

Append to `src/lib/components/workos/lib/store.test.ts` (bottom of file). Also add `loadBootstrap`, `openTaskById`, `selectedTaskId`, `inboxTask`, `workstreams`, `workspaces`, `teams`, `myTasks` to the existing `import { … } from './store';` line if not already there:

```ts
describe('openTaskById (URL deep-link open)', () => {
	beforeEach(() => {
		tasks.set([]);
		myTasks.set([]);
		inboxTask.set(null);
		selectedTaskId.set(null);
	});

	it('opens directly when the task is already in the workstream list', async () => {
		tasks.set([mk({ id: 'in-list' })]);
		const ok = await openTaskById('in-list');
		expect(ok).toBe(true);
		expect(get(selectedTaskId)).toBe('in-list');
		expect(get(inboxTask)).toBeNull(); // no fetch fallback needed
	});

	it('falls back to a direct fetch when the task is in no local list', async () => {
		const ok = await openTaskById('folded'); // mocked getTask returns id 'folded'
		expect(ok).toBe(true);
		expect(get(selectedTaskId)).toBe('folded');
		expect(get(inboxTask)?.id).toBe('folded');
	});

	it('returns false when the fetch fails, leaving selection untouched', async () => {
		const api = await import('./api');
		(api.getTask as any).mockRejectedValueOnce(Object.assign(new Error('nope'), { status: 404 }));
		const ok = await openTaskById('ghost');
		expect(ok).toBe(false);
		expect(get(selectedTaskId)).toBeNull();
		expect(get(inboxTask)).toBeNull();
	});
});

describe('loadBootstrap selectDefaultWorkstream option', () => {
	it('skips the default workstream selection when told to', async () => {
		const api = await import('./api');
		(api.getBootstrap as any).mockResolvedValueOnce({
			teams: [{ id: 'tm', name: 'T' }],
			workspaces: [{ id: 'wsp', team_id: 'tm', name: 'W', visibility: 'team' }],
			workstreams: [{ id: 'w1', workspace_id: 'wsp', name: 'S' }],
			roles: { tm: 'member' }
		});
		currentWorkstreamId.set(null);
		await loadBootstrap({ selectDefaultWorkstream: false });
		expect(get(currentWorkstreamId)).toBeNull();
	});

	it('still auto-selects by default (regression)', async () => {
		const api = await import('./api');
		(api.getBootstrap as any).mockResolvedValueOnce({
			teams: [{ id: 'tm', name: 'T' }],
			workspaces: [{ id: 'wsp', team_id: 'tm', name: 'W', visibility: 'team' }],
			workstreams: [{ id: 'w1', workspace_id: 'wsp', name: 'S' }],
			roles: { tm: 'member' }
		});
		currentWorkstreamId.set(null);
		currentTeamId.set('tm');
		await loadBootstrap();
		expect(get(currentWorkstreamId)).toBe('w1');
	});
});
```

Note: the existing top-of-file `vi.mock('./api', …)` already stubs `getBootstrap`, `getTask`, `listTasks`, `getDirectory` may be MISSING — check the mock block; if `getDirectory` and `getNotificationCounts` are absent add `getDirectory: vi.fn(async () => [])` to it (loadBootstrap calls it). Also import `currentTeamId` if not imported.

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `npx vitest run src/lib/components/workos/lib/store.test.ts`
Expected: FAIL — `openTaskById` is not exported; the `selectDefaultWorkstream` test fails because the option is ignored (workstream gets selected anyway). Pre-existing tests must still pass.

- [ ] **Step 3: Implement both changes in `store.ts`**

Change 1 — `loadBootstrap` signature (line ~211) and its last body line (~232):

```ts
export async function loadBootstrap(opts: { selectDefaultWorkstream?: boolean } = {}): Promise<void> {
```

```ts
		// URL deep links (urlSync.hydrateFromUrl) perform their own selection;
		// skipping the default here keeps it to exactly one selectWorkstream
		// call per load (spec: bootstrap default-selection interplay).
		if (opts.selectDefaultWorkstream !== false && firstStream && !get(currentWorkstreamId))
			await selectWorkstream(firstStream.id);
```

Change 2 — new function directly after `openInboxNotification` (after line ~706):

```ts
/**
 * Deep-link task open (URL `task` param): the id may live outside both the
 * loaded workstream list and My Work. Local lists first; otherwise fetch the
 * row directly and park it in `inboxTask` — the first slot in the
 * `selectedTask` derivation — joining its workstream room so realtime keeps
 * the drawer fresh (same mechanics as the inbox split-pane; closeTask()
 * undoes all of it). Returns false when the task is gone or unreadable —
 * 404 and 403 are indistinguishable by design (see the access reference).
 */
export async function openTaskById(id: string): Promise<boolean> {
	if (get(tasks).some((t) => t.id === id) || get(myTasks).some((t) => t.id === id)) {
		openTask(id);
		return true;
	}
	let t: Task | null = null;
	try {
		t = await api.getTask(token(), id);
	} catch {
		t = null; // transient failures also report false: a deep link has no retry UI
	}
	if (!t) return false;
	if (inboxRoomKey) {
		leaveRoom(inboxRoomKey);
		inboxRoomKey = null;
	}
	inboxRoomKey = streamKey(t.workstream_id);
	enterRoom(inboxRoomKey);
	// inboxTask BEFORE selectedTaskId so the drawer renders once, with data.
	inboxTask.set(t);
	selectedTaskId.set(id);
	void loadTaskDetail(id);
	return true;
}
```

- [ ] **Step 4: Run the full store suite**

Run: `npx vitest run src/lib/components/workos/lib/store.test.ts`
Expected: PASS — new tests green, zero regressions.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/store.ts src/lib/components/workos/lib/store.test.ts
git commit -m "feat(workos): openTaskById deep-link fallback + optional bootstrap default-select"
```

---

### Task 3: URL sync wiring (`urlSync.ts`)

**Files:**
- Create: `src/lib/components/workos/lib/urlSync.ts`
- Test: `src/lib/components/workos/lib/urlSync.test.ts`

**Interfaces:**
- Consumes: Task 1's `buildQuery`/`parseQuery`/`decideOp`/`WORKSTREAM_VIEWS`/`NavState`; Task 2's `openTaskById`; existing store exports `view`, `currentTeamId`, `currentWorkstreamId`, `selectedTaskId`, `workspaces`, `workstreams`, `selectTeam`, `selectWorkstream`, `closeTask`; SvelteKit `pushState`/`replaceState` (`$app/navigation`), `page` (`$app/stores`), `browser` (`$app/environment`); `toast` (`svelte-sonner`).
- Produces (used by Task 4):
  - `urlHasWorkstream(): boolean`
  - `hydrateFromUrl(search?: string): Promise<void>` — call once after `loadBootstrap`
  - `initUrlSync(): void` — call after `hydrateFromUrl`
  - `destroyUrlSync(): void` — call in `onDestroy`

- [ ] **Step 1: Write the failing tests**

Create `src/lib/components/workos/lib/urlSync.test.ts`. Vitest runs in **node** env (no jsdom): `localStorage` must be stubbed via `vi.hoisted` BEFORE the store module loads (we mock `browser: true`, which makes store.ts touch localStorage at module init). `window` is never touched — `hydrateFromUrl` takes the search string as an argument.

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';

vi.hoisted(() => {
	const bag = new Map<string, string>();
	(globalThis as any).localStorage = {
		getItem: (k: string) => bag.get(k) ?? null,
		setItem: (k: string, v: string) => void bag.set(k, v),
		removeItem: (k: string) => void bag.delete(k),
		clear: () => bag.clear(),
		key: () => null,
		get length() { return bag.size; }
	};
});

vi.mock('$app/environment', () => ({ browser: true }));
vi.mock('$app/navigation', () => ({
	pushState: vi.fn(),
	replaceState: vi.fn()
}));
const pageStore = vi.hoisted(() => {
	// Deferred require: vi.hoisted runs before ESM imports are evaluated.
	const { writable } = require('svelte/store');
	return writable({ url: new URL('http://localhost/workos') });
});
vi.mock('$app/stores', () => ({ page: pageStore }));
vi.mock('svelte-sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock('$lib/stores', () => {
	const { writable } = require('svelte/store');
	return { socket: writable(null), user: writable({ id: 'u1', name: 'Lara', role: 'user' }) };
});
vi.mock('./api', () => ({
	getBootstrap: vi.fn(async () => ({ teams: [], workspaces: [], workstreams: [], roles: {} })),
	getDirectory: vi.fn(async () => []),
	listTasks: vi.fn(async () => [
		{
			id: 't-in-list', workstream_id: 'w1', team_id: 'tm', number: 1, key: 'OSL-1', title: 'listed',
			status: 'todo', priority: null, assignee_ids: ['u1'], progress: 0, labels: [], sort_key: 1,
			created_by_id: 'u1', created_at: 0, updated_at: 0
		}
	]),
	listLabels: vi.fn(async () => []),
	getTask: vi.fn(async (t: string, id: string) => ({
		id, workstream_id: 'w-other', team_id: 'tm', number: 9, key: 'OSL-9', title: 'fetched',
		status: 'todo', priority: null, assignee_ids: ['u1'], progress: 0, labels: [], sort_key: 1,
		created_by_id: 'u1', created_at: 0, updated_at: 0
	})),
	listSubtasks: vi.fn(async () => []),
	listComments: vi.fn(async () => []),
	listActivity: vi.fn(async () => []),
	listAttachments: vi.fn(async () => [])
}));

import { pushState, replaceState } from '$app/navigation';
import { toast } from 'svelte-sonner';
import {
	view, currentTeamId, currentWorkstreamId, selectedTaskId,
	teams, workspaces, workstreams, tasks, closeTask
} from './store';
import { hydrateFromUrl, initUrlSync, destroyUrlSync, urlHasWorkstream } from './urlSync';

const flush = () => new Promise((r) => setTimeout(r, 0));

const seedTree = () => {
	teams.set([{ id: 'tm', name: 'Team' } as any, { id: 'tm2', name: 'Team 2' } as any]);
	workspaces.set([
		{ id: 'wsp', team_id: 'tm', name: 'W', visibility: 'team' } as any,
		{ id: 'wsp2', team_id: 'tm2', name: 'W2', visibility: 'team' } as any
	]);
	workstreams.set([
		{ id: 'w1', workspace_id: 'wsp', name: 'S' } as any,
		{ id: 'w2', workspace_id: 'wsp2', name: 'S2' } as any
	]);
};

beforeEach(() => {
	destroyUrlSync();
	vi.clearAllMocks();
	seedTree();
	view.set('mywork');
	currentTeamId.set('tm');
	currentWorkstreamId.set(null);
	closeTask();
	tasks.set([]);
	pageStore.set({ url: new URL('http://localhost/workos') });
});

describe('hydrateFromUrl', () => {
	it('valid ws deep link selects the workstream and view', async () => {
		await hydrateFromUrl('?view=list&ws=w1');
		expect(get(currentWorkstreamId)).toBe('w1');
		expect(get(view)).toBe('list');
	});

	it('ws in another team switches the team first', async () => {
		await hydrateFromUrl('?view=board&ws=w2');
		expect(get(currentTeamId)).toBe('tm2');
		expect(get(currentWorkstreamId)).toBe('w2');
	});

	it('unknown ws falls back to My Work with a toast', async () => {
		await hydrateFromUrl('?view=board&ws=ghost&task=t1');
		expect(toast.error).toHaveBeenCalledWith('Workstream not available');
		expect(get(view)).toBe('mywork');
		expect(get(currentWorkstreamId)).toBeNull();
		expect(get(selectedTaskId)).toBeNull();
		// address bar got canonicalized to the fallback state
		expect(replaceState).toHaveBeenCalledWith('/workos', {});
	});

	it('task in the loaded list opens without a fetch fallback', async () => {
		await hydrateFromUrl('?view=board&ws=w1&task=t-in-list');
		expect(get(selectedTaskId)).toBe('t-in-list');
	});

	it('task outside all lists opens via direct fetch', async () => {
		await hydrateFromUrl('?task=t-anywhere');
		expect(get(selectedTaskId)).toBe('t-anywhere');
	});

	it('dead task id drops the param with a toast, view survives', async () => {
		const api = await import('./api');
		(api.getTask as any).mockRejectedValueOnce(Object.assign(new Error('gone'), { status: 404 }));
		await hydrateFromUrl('?view=list&ws=w1&task=dead');
		expect(toast.error).toHaveBeenCalledWith('Task not available');
		expect(get(view)).toBe('list');
		expect(get(currentWorkstreamId)).toBe('w1');
		expect(get(selectedTaskId)).toBeNull();
		expect(replaceState).toHaveBeenCalledWith('/workos?view=list&ws=w1', {});
	});
});

describe('store → URL writes', () => {
	it('view change pushes one history entry', async () => {
		await hydrateFromUrl('');
		initUrlSync();
		view.set('inbox');
		await flush();
		expect(pushState).toHaveBeenCalledTimes(1);
		expect(pushState).toHaveBeenCalledWith('/workos?view=inbox', {});
	});

	it('compound ws switch (ws set + task cleared) is one push', async () => {
		await hydrateFromUrl('?view=board&ws=w1&task=t-in-list');
		initUrlSync();
		const { selectWorkstream } = await import('./store');
		await selectWorkstream('w2'); // sets ws AND clears task
		await flush();
		expect(pushState).toHaveBeenCalledTimes(1);
		expect(pushState).toHaveBeenCalledWith('/workos?view=board&ws=w2', {});
	});

	it('task-only change replaces, never pushes', async () => {
		await hydrateFromUrl('?view=board&ws=w1');
		initUrlSync();
		vi.mocked(replaceState).mockClear(); // ignore hydrate canonicalization
		selectedTaskId.set('t-in-list');
		await flush();
		expect(pushState).not.toHaveBeenCalled();
		expect(replaceState).toHaveBeenCalledWith('/workos?view=board&ws=w1&task=t-in-list', {});
	});

	it('no-op transitions write nothing', async () => {
		await hydrateFromUrl('?view=inbox');
		initUrlSync();
		vi.mocked(replaceState).mockClear();
		view.set('inbox'); // same value
		await flush();
		expect(pushState).not.toHaveBeenCalled();
		expect(replaceState).not.toHaveBeenCalled();
	});
});

describe('URL → store (Back/Forward via page store)', () => {
	it('a popstate URL re-hydrates the stores', async () => {
		await hydrateFromUrl('?view=board&ws=w1');
		initUrlSync();
		pageStore.set({ url: new URL('http://localhost/workos?view=inbox') });
		await flush();
		expect(get(view)).toBe('inbox');
	});

	it('closes the drawer when the restored URL has no task', async () => {
		await hydrateFromUrl('?view=board&ws=w1&task=t-in-list');
		initUrlSync();
		pageStore.set({ url: new URL('http://localhost/workos?view=board&ws=w1') });
		await flush();
		expect(get(selectedTaskId)).toBeNull();
	});

	it('reflected self-written URLs cause no extra history writes (loop guard)', async () => {
		await hydrateFromUrl('');
		initUrlSync();
		view.set('inbox');
		await flush();
		expect(pushState).toHaveBeenCalledTimes(1);
		vi.mocked(replaceState).mockClear();
		// simulate SvelteKit reflecting our own pushState back into the page store
		pageStore.set({ url: new URL('http://localhost/workos?view=inbox') });
		await flush();
		expect(pushState).toHaveBeenCalledTimes(1); // no ping-pong
		expect(replaceState).not.toHaveBeenCalled();
		expect(get(view)).toBe('inbox');
	});

	it('ignores URLs outside /workos', async () => {
		await hydrateFromUrl('?view=board&ws=w1');
		initUrlSync();
		pageStore.set({ url: new URL('http://localhost/c/abc123?view=inbox') });
		await flush();
		expect(get(view)).toBe('board');
	});
});
```

Note on `urlHasWorkstream`: it reads `window.location` and is therefore NOT unit-tested in node env (two-line function, covered by the smoke checklist). Do not add a test that touches `window`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/lib/components/workos/lib/urlSync.test.ts`
Expected: FAIL — `Cannot find module './urlSync'`.

- [ ] **Step 3: Write the implementation**

Create `src/lib/components/workos/lib/urlSync.ts`:

```ts
// Store <-> URL wiring for WorkOS deep linking. The ONLY place that knows the
// URL exists: views/sidebar keep calling selectWorkstream/openTask/view.set,
// and this module mirrors those stores into `?view=…&ws=…&task=…` (and back).
//
// Two one-way flows with a loop guard between them:
//   stores → URL  (scheduleWrite: push on view/ws change, replace on task)
//   URL → stores  (applyUrl: initial hydrate + Back/Forward via page store)
import { get } from 'svelte/store';
import { browser } from '$app/environment';
import { pushState, replaceState } from '$app/navigation';
import { page } from '$app/stores';
import { toast } from 'svelte-sonner';
import {
	view, currentTeamId, currentWorkstreamId, selectedTaskId,
	workspaces, workstreams,
	selectTeam, selectWorkstream, openTaskById, closeTask
} from './store';
import { buildQuery, parseQuery, decideOp, WORKSTREAM_VIEWS, type NavState } from './urlState';

const BASE = '/workos';

let prevState: NavState | null = null; // baseline for decideOp; null = not initialized
let lastWritten: string | null = null; // canonical search we last put in the address bar
let applying = false; // URL→store application in progress: suppress echo writes
let writeQueued = false;
let unsubs: Array<() => void> = [];

function currentNavState(): NavState {
	const v = get(view);
	return {
		view: v,
		// A selected workstream is real state even on global views — but it is
		// not part of THEIR address. buildQuery would drop it anyway; nulling it
		// here keeps decideOp from seeing a phantom ws change.
		ws: WORKSTREAM_VIEWS.has(v) ? get(currentWorkstreamId) : null,
		task: get(selectedTaskId)
	};
}

// Stores → URL. Coalesced to a microtask so a compound transition (e.g.
// selectWorkstream sets ws AND clears task) writes one history entry.
function scheduleWrite(): void {
	if (!browser || applying || writeQueued) return;
	writeQueued = true;
	queueMicrotask(() => {
		writeQueued = false;
		if (applying || prevState === null) return;
		const next = currentNavState();
		const op = decideOp(prevState, next);
		prevState = next;
		if (op === 'none') return;
		const q = buildQuery(next);
		lastWritten = q;
		if (op === 'push') pushState(`${BASE}${q}`, {});
		else replaceState(`${BASE}${q}`, {});
	});
}

// URL → stores. Shared by the initial hydrate and Back/Forward. Every step
// goes through the existing store functions so room ref-counting and the
// "user moved on" guards apply unchanged. Falls back without blank screens:
// bad ws → My Work, bad task → param dropped. Ends by canonicalizing the
// address bar when it drifted from what actually got applied.
async function applyUrl(params: URLSearchParams, rawSearch: string): Promise<void> {
	applying = true;
	try {
		let { view: v, ws, task } = parseQuery(params);

		if (ws && ws !== get(currentWorkstreamId)) {
			const stream = get(workstreams).find((s) => s.id === ws);
			const parent = stream ? get(workspaces).find((w) => w.id === stream.workspace_id) : undefined;
			if (stream && parent) {
				// URL wins over the localStorage team when they disagree — link
				// sharing is the point (spec: team conflict rule).
				if (get(currentTeamId) !== parent.team_id) await selectTeam(parent.team_id);
				await selectWorkstream(ws);
			} else {
				// Deleted, no access (bootstrap is server-trimmed), or garbage —
				// indistinguishable by design, one fallback for all three.
				toast.error('Workstream not available');
				v = 'mywork';
				ws = null;
				task = null;
			}
		}

		if (get(view) !== v) view.set(v);

		const openId = get(selectedTaskId);
		if (task && task !== openId) {
			if (!(await openTaskById(task))) {
				toast.error('Task not available');
				task = null;
			}
		} else if (!task && openId) {
			closeTask(); // Back to a drawerless entry must close the drawer
		}

		prevState = currentNavState();
		const canonical = buildQuery(prevState);
		lastWritten = canonical;
		if (canonical !== rawSearch) replaceState(`${BASE}${canonical}`, {});
	} finally {
		applying = false;
	}
}

/**
 * True when the current URL carries a `ws` param — WorkOSApp uses this to
 * skip bootstrap's default workstream selection so a deep-linked load does
 * exactly one selectWorkstream call (spec: default-selection interplay).
 */
export function urlHasWorkstream(): boolean {
	return browser && new URLSearchParams(window.location.search).has('ws');
}

/** One-shot initial hydrate. Call after loadBootstrap(), before initUrlSync(). */
export async function hydrateFromUrl(search?: string): Promise<void> {
	if (!browser) return;
	const raw = search ?? window.location.search;
	await applyUrl(new URLSearchParams(raw), raw);
}

export function initUrlSync(): void {
	if (!browser) return;
	prevState = currentNavState();
	// Anything that moved state between hydrate and init (e.g. the admin-view
	// guard snapping a non-admin off ?view=admin) drifts the address bar;
	// reconcile once so lastWritten always matches reality.
	const q = buildQuery(prevState);
	if (lastWritten !== q) {
		lastWritten = q;
		replaceState(`${BASE}${q}`, {});
	}
	unsubs.push(view.subscribe(scheduleWrite));
	unsubs.push(currentWorkstreamId.subscribe(scheduleWrite));
	unsubs.push(selectedTaskId.subscribe(scheduleWrite));
	// Back/Forward (and any external URL change): SvelteKit reflects it into
	// the page store; self-written URLs are recognized by string equality
	// against the canonical form we always write.
	unsubs.push(
		page.subscribe(($p) => {
			if (!$p.url.pathname.endsWith(BASE)) return;
			if (applying) return;
			// URL.search is '' for no params and '?…' otherwise — exactly
			// buildQuery's output, so one string comparison recognizes our
			// own writes.
			if ($p.url.search === lastWritten) return;
			void applyUrl($p.url.searchParams, $p.url.search);
		})
	);
}

export function destroyUrlSync(): void {
	for (const u of unsubs) u();
	unsubs = [];
	prevState = null;
	lastWritten = null;
	applying = false;
	writeQueued = false;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/lib/components/workos/lib/urlSync.test.ts`
Expected: PASS. If the loop-guard test fails on the initial `page.subscribe` immediate call: the subscription fires synchronously with the CURRENT page value on subscribe — that value's search will not match `lastWritten` when the page-store mock was never updated after hydrate; the guard must therefore compare against the canonical form, which `applyUrl` just wrote. Fix by making sure `hydrateFromUrl` ran before `initUrlSync` in the test (it does) and that `lastWritten` is set in `applyUrl` BEFORE the `replaceState` call.

- [ ] **Step 5: Run the whole workos lib suite for regressions**

Run: `npx vitest run src/lib/components/workos/lib/`
Expected: PASS — all files green.

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/workos/lib/urlSync.ts src/lib/components/workos/lib/urlSync.test.ts
git commit -m "feat(workos): URL sync wiring — pushState nav history + deep-link hydration"
```

---

### Task 4: Wire into `WorkOSApp.svelte` + doc note + static verify

**Files:**
- Modify: `src/lib/components/workos/WorkOSApp.svelte:35-39` (onMount/onDestroy)
- Modify: `docs/superpowers/specs/2026-06-26-workos-access-control.md` (§6, one bullet)

**Interfaces:**
- Consumes: Task 3's `urlHasWorkstream`/`hydrateFromUrl`/`initUrlSync`/`destroyUrlSync`; Task 2's `loadBootstrap` option.
- Produces: the feature, live.

- [ ] **Step 1: Edit `WorkOSApp.svelte`**

Add to the imports (after the `./lib/store` import block):

```ts
	import { hydrateFromUrl, initUrlSync, destroyUrlSync, urlHasWorkstream } from './lib/urlSync';
```

Replace the existing onMount/onDestroy:

```ts
	onMount(async () => {
		// Deep link present → hydrateFromUrl performs the one workstream
		// selection; otherwise bootstrap picks its default as before.
		await loadBootstrap({ selectDefaultWorkstream: !urlHasWorkstream() });
		await hydrateFromUrl();
		initUrlSync();
		connectRealtime();
	});
	onDestroy(() => {
		destroyUrlSync();
		disconnectRealtime();
	});
```

- [ ] **Step 2: Append the access-doc note**

In `docs/superpowers/specs/2026-06-26-workos-access-control.md`, §6 (Frontend consumption), add a bullet at the end of the list:

```markdown
- **URL deep links (2026-07-20)** — `/workos?view=…&ws=…&task=…` (urlSync.ts) adds
  NO frontend access logic: `ws` is validated against the server-trimmed bootstrap
  tree, `task` resolves via `GET /tasks/{id}` (404 for missing AND forbidden — one
  client fallback path, no exists/forbidden oracle). Pasting `?view=admin` without
  the permission is snapped away by the existing WorkOSApp guard.
```

And add a line to the header changelog comment block at the top of the file:

```
  2026-07-20: URL deep linking shipped (query-param sync, urlSync.ts). §6 gains a
  bullet; no access logic changed.
```

- [ ] **Step 3: Static verify + full frontend tests**

Run: `npm run check`
Expected: exit 0 for the touched files — no NEW errors introduced (the repo may have pre-existing warnings; compare against `git stash` baseline only if in doubt).

Run: `npm run test:frontend`
Expected: PASS — entire frontend suite green.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/WorkOSApp.svelte docs/superpowers/specs/2026-06-26-workos-access-control.md
git commit -m "feat(workos): enable URL deep linking in the shell + access-doc note"
```

---

### Task 5: Manual browser smoke (user-gated)

**Files:** none — verification only.

Frontend edits are live on the user's own Vite hot-reload server. **Do NOT start a dev server or open a preview without asking the user first** (standing rule). Present this checklist and run it together, or hand it over:

- [ ] 1. Copy a board URL (`?view=board&ws=…`) → open in a new tab → same board, same workstream, sidebar highlights it.
- [ ] 2. Open a task, copy the URL → new tab → board renders with the drawer open on that task.
- [ ] 3. Refresh mid-board → same place (no snap back to My Work).
- [ ] 4. Back-walk: board ws-A → list ws-A → board ws-B → Back → list ws-A → Back → board ws-A → Back → leaves WorkOS.
- [ ] 5. Open + close the task drawer several times → Back still exits one major nav per press (no drawer entries).
- [ ] 6. Deep link to a task in ANOTHER team → team switches, drawer opens.
- [ ] 7. Paste a URL with a deleted/garbage task id → toast "Task not available", the view survives, param vanishes from the address bar.
- [ ] 8. Paste a URL with a garbage ws id → toast "Workstream not available", lands on My Work.
- [ ] 9. Non-admin pastes `?view=admin` → lands on board, URL rewrites itself.
- [ ] 10. My Work / Inbox URLs carry no `ws` param; plain `/workos` = My Work.
- [ ] 11. Realtime sanity: after a deep-linked task open, a comment added from another session appears live in the drawer (room join happened).

If all pass: report results. Any failure: superpowers:systematic-debugging before touching code.

---

## Self-Review Notes (already applied)

- Spec coverage: §1 scheme → Task 1; §2 architecture → Task 3; §3 hydrate/fallbacks/bootstrap-interplay → Tasks 2+3+4; §4 testing → each task's tests + Task 5 checklist. The spec's "store functions are not modified" line is honored in spirit: both store.ts changes are strictly additive (new function; new option defaulting to old behavior); the existing suite proves it.
- Type consistency: `NavState`/`buildQuery`/`parseQuery`/`decideOp`/`WORKSTREAM_VIEWS` (Task 1) match Task 3's imports; `openTaskById`/`loadBootstrap(opts)` (Task 2) match Tasks 3/4's usage.
- Known judgment call: transient network failure on a deep-linked task fetch also reports "Task not available" (no retry UI on a deep link); the inbox path keeps its richer gone-vs-transient split.
