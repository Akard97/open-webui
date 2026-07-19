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

// Node env has no window: stub the slice urlSync touches -- location (read by
// hydrateFromUrl/urlHasWorkstream/the popstate handler) and popstate listener
// registration. Browser semantics this stub preserves: programmatic
// pushState/replaceState update location WITHOUT firing popstate; only real
// history traversal (simulated via win.__go below) fires it.
const win = vi.hoisted(() => {
	const listeners = new Set<() => void>();
	const w = {
		location: { href: 'http://localhost/workos', pathname: '/workos', search: '' },
		addEventListener: (type: string, fn: () => void) => { if (type === 'popstate') listeners.add(fn); },
		removeEventListener: (type: string, fn: () => void) => { if (type === 'popstate') listeners.delete(fn); },
		__setUrl(href: string) {
			const u = new URL(href, 'http://localhost');
			w.location.href = u.href;
			w.location.pathname = u.pathname;
			w.location.search = u.search;
		},
		// Simulate the browser Back/Forward: location updates FIRST, then
		// popstate fires with it already in place.
		__go(href: string) {
			w.__setUrl(href);
			for (const fn of [...listeners]) fn();
		},
		__listenerCount: () => listeners.size
	};
	(globalThis as any).window = w;
	return w;
});

vi.mock('$app/navigation', () => ({
	// Mirror the real browser: programmatic history writes update the address
	// bar but never fire popstate.
	pushState: vi.fn((url: string) => win.__setUrl(url)),
	replaceState: vi.fn((url: string) => win.__setUrl(url))
}));
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

// Keep the stubbed address bar consistent with what hydrateFromUrl is told to
// read -- in a real browser they are the same thing.
const hydrate = async (s: string) => {
	win.__setUrl(`/workos${s}`);
	await hydrateFromUrl(s);
};

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
	win.__setUrl('/workos');
});

describe('hydrateFromUrl', () => {
	it('valid ws deep link selects the workstream and view', async () => {
		await hydrate('?view=list&ws=w1');
		expect(get(currentWorkstreamId)).toBe('w1');
		expect(get(view)).toBe('list');
	});

	it('ws in another team switches the team first', async () => {
		await hydrate('?view=board&ws=w2');
		expect(get(currentTeamId)).toBe('tm2');
		expect(get(currentWorkstreamId)).toBe('w2');
	});

	it('unknown ws falls back to My Work with a toast', async () => {
		await hydrate('?view=board&ws=ghost&task=t1');
		expect(toast.error).toHaveBeenCalledWith('Workstream not available');
		expect(get(view)).toBe('mywork');
		expect(get(currentWorkstreamId)).toBeNull();
		expect(get(selectedTaskId)).toBeNull();
		// address bar got canonicalized to the fallback state
		expect(replaceState).toHaveBeenCalledWith('/workos', {});
	});

	it('task in the loaded list opens without a fetch fallback', async () => {
		await hydrate('?view=board&ws=w1&task=t-in-list');
		expect(get(selectedTaskId)).toBe('t-in-list');
	});

	it('task outside all lists opens via direct fetch', async () => {
		await hydrate('?task=t-anywhere');
		expect(get(selectedTaskId)).toBe('t-anywhere');
	});

	it('dead task id drops the param with a toast, view survives', async () => {
		const api = await import('./api');
		(api.getTask as any).mockRejectedValueOnce(Object.assign(new Error('gone'), { status: 404 }));
		await hydrate('?view=list&ws=w1&task=dead');
		expect(toast.error).toHaveBeenCalledWith('Task not available');
		expect(get(view)).toBe('list');
		expect(get(currentWorkstreamId)).toBe('w1');
		expect(get(selectedTaskId)).toBeNull();
		expect(replaceState).toHaveBeenCalledWith('/workos?view=list&ws=w1', {});
	});

	it('drops a hand-edited ?view=admin at parse time for a non-admin user', async () => {
		// $lib/stores is mocked above with a role:'user' user -- canUseAdmin is false.
		await hydrate('?view=admin');
		expect(get(view)).toBe('mywork');
		expect(replaceState).toHaveBeenCalledWith('/workos', {});
	});
});

describe('view/workstream apply ordering (no My Work flash)', () => {
	it('applies the parsed view before awaiting the workstream switch', async () => {
		const api = await import('./api');
		let release!: (rows: unknown[]) => void;
		const hang = new Promise<unknown[]>((r) => { release = r; });
		(api.listTasks as any).mockImplementationOnce(() => hang);
		const p = hydrate('?view=board&ws=w1'); // not awaited yet
		await Promise.resolve(); // let applyUrl run up to the still-pending listTasks call
		// view flips immediately -- MyWorkView never mounts for this window.
		expect(get(view)).toBe('board');
		release([]);
		await p;
		expect(get(currentWorkstreamId)).toBe('w1'); // final state unchanged from before
	});
});

describe('store → URL writes', () => {
	it('view change pushes one history entry', async () => {
		await hydrate('');
		initUrlSync();
		view.set('inbox');
		await flush();
		expect(pushState).toHaveBeenCalledTimes(1);
		expect(pushState).toHaveBeenCalledWith('/workos?view=inbox', {});
	});

	it('compound ws switch (ws set + task cleared) is one push', async () => {
		await hydrate('?view=board&ws=w1&task=t-in-list');
		initUrlSync();
		const { selectWorkstream } = await import('./store');
		await selectWorkstream('w2'); // sets ws AND clears task
		await flush();
		expect(pushState).toHaveBeenCalledTimes(1);
		expect(pushState).toHaveBeenCalledWith('/workos?view=board&ws=w2', {});
	});

	it('task-only change replaces, never pushes', async () => {
		await hydrate('?view=board&ws=w1');
		initUrlSync();
		vi.mocked(replaceState).mockClear(); // ignore hydrate canonicalization
		selectedTaskId.set('t-in-list');
		await flush();
		expect(pushState).not.toHaveBeenCalled();
		expect(replaceState).toHaveBeenCalledWith('/workos?view=board&ws=w1&task=t-in-list', {});
	});

	it('no-op transitions write nothing', async () => {
		await hydrate('?view=inbox');
		initUrlSync();
		vi.mocked(replaceState).mockClear();
		view.set('inbox'); // same value
		await flush();
		expect(pushState).not.toHaveBeenCalled();
		expect(replaceState).not.toHaveBeenCalled();
	});
});

describe('URL → store (Back/Forward via native popstate)', () => {
	it('a popstate URL re-hydrates the stores', async () => {
		await hydrate('?view=board&ws=w1');
		initUrlSync();
		win.__go('/workos?view=inbox');
		await flush();
		expect(get(view)).toBe('inbox');
	});

	it('closes the drawer when the restored URL has no task', async () => {
		await hydrate('?view=board&ws=w1&task=t-in-list');
		initUrlSync();
		win.__go('/workos?view=board&ws=w1');
		await flush();
		expect(get(selectedTaskId)).toBeNull();
	});

	it('a nav click is never reverted by its own URL write (Kit 2.59 regression)', async () => {
		// The original page-store echo detection failed here: $app/stores does
		// not track shallow-routing pushState, so after a click its emission
		// still carried the OLD url, applyUrl re-applied it, and the click was
		// reverted (verified live). With popstate there is no emission at all
		// for programmatic writes -- the clicked state must simply survive.
		await hydrate('');
		initUrlSync();
		view.set('inbox'); // sidebar click
		await flush();
		expect(pushState).toHaveBeenCalledTimes(1);
		expect(pushState).toHaveBeenCalledWith('/workos?view=inbox', {});
		expect(get(view)).toBe('inbox'); // NOT snapped back to mywork
		vi.mocked(replaceState).mockClear();
		await flush();
		expect(replaceState).not.toHaveBeenCalled(); // and no correcting rewrite either
	});

	it('a popstate matching our own last write is a no-op (safety net)', async () => {
		await hydrate('');
		initUrlSync();
		view.set('inbox');
		await flush();
		vi.mocked(pushState).mockClear();
		vi.mocked(replaceState).mockClear();
		win.__go('/workos?view=inbox'); // traversal landing on the same URL we wrote
		await flush();
		expect(pushState).not.toHaveBeenCalled();
		expect(replaceState).not.toHaveBeenCalled();
		expect(get(view)).toBe('inbox');
	});

	it('ignores popstate outside /workos', async () => {
		await hydrate('?view=board&ws=w1');
		initUrlSync();
		win.__go('/c/abc123?view=inbox');
		await flush();
		expect(get(view)).toBe('board');
	});

	it('destroyUrlSync removes the popstate listener', async () => {
		await hydrate('');
		initUrlSync();
		expect(win.__listenerCount()).toBe(1);
		destroyUrlSync();
		expect(win.__listenerCount()).toBe(0);
	});
});

describe('concurrent URL application (queue-latest)', () => {
	it('a navigation that arrives while one is still applying is not dropped', async () => {
		await hydrate('?view=board&ws=w1');
		initUrlSync();
		const api = await import('./api');
		let release!: (t: unknown) => void;
		const hang = new Promise((r) => { release = r; });
		// 'slow-task' is in neither `tasks` nor `myTasks`, so openTaskById takes
		// the fetch-fallback branch -- this is where the first applyUrl call
		// gets stuck awaiting.
		(api.getTask as any).mockImplementationOnce(() => hang);
		win.__go('/workos?view=board&ws=w1&task=slow-task');
		await Promise.resolve(); // let the first applyUrl start and reach its await
		// Second navigation arrives mid-flight -- must be queued, not dropped.
		win.__go('/workos?view=inbox');
		release({
			id: 'slow-task', workstream_id: 'w-other', team_id: 'tm', number: 9, key: 'OSL-9', title: 'fetched',
			status: 'todo', priority: null, assignee_ids: ['u1'], progress: 0, labels: [], sort_key: 1,
			created_by_id: 'u1', created_at: 0, updated_at: 0
		});
		await flush();
		expect(get(view)).toBe('inbox'); // latest navigation wins
		expect(get(selectedTaskId)).toBeNull(); // reconciled by the second apply (no task param)
	});
});

describe('destroyUrlSync during an in-flight applyUrl (route left mid-fetch)', () => {
	it('does not rewrite the address bar or the store once the fetch resolves', async () => {
		await hydrate('?view=board&ws=w1');
		initUrlSync();
		const api = await import('./api');
		let release!: (t: unknown) => void;
		const hang = new Promise((r) => { release = r; });
		// 'slow-task' is in neither `tasks` nor `myTasks`, so openTaskById takes
		// the fetch-fallback branch -- this is where applyUrl gets stuck.
		(api.getTask as any).mockImplementationOnce(() => hang);
		win.__go('/workos?view=board&ws=w1&task=slow-task');
		await Promise.resolve(); // let applyUrl start and reach its await
		destroyUrlSync(); // simulates leaving /workos mid-flight
		vi.mocked(pushState).mockClear();
		vi.mocked(replaceState).mockClear();
		release({
			id: 'slow-task', workstream_id: 'w-other', team_id: 'tm', number: 9, key: 'OSL-9', title: 'fetched',
			status: 'todo', priority: null, assignee_ids: ['u1'], progress: 0, labels: [], sort_key: 1,
			created_by_id: 'u1', created_at: 0, updated_at: 0
		});
		await flush();
		expect(pushState).not.toHaveBeenCalled();
		expect(replaceState).not.toHaveBeenCalled();
		expect(get(selectedTaskId)).toBeNull(); // the stale open was undone, not left half-applied
	});

	it('does not close a drawer a competing open now owns, even when it is the SAME id', async () => {
		await hydrate('?view=board&ws=w1');
		initUrlSync();
		const api = await import('./api');
		const { inboxTask } = await import('./store');
		let release!: (t: unknown) => void;
		const hang = new Promise((r) => { release = r; });
		(api.getTask as any).mockImplementationOnce(() => hang);
		win.__go('/workos?view=board&ws=w1&task=slow-task');
		await Promise.resolve(); // let applyUrl start and reach its await inside openTaskById
		destroyUrlSync(); // route left -- this applyUrl call is now stale
		// A competing open (a fresh session's own deep-link open, or a manual
		// click) commits the SAME id first while the orphaned fetch is still
		// hung -- id equality alone must not read as "the stale call owns it".
		selectedTaskId.set('slow-task');
		inboxTask.set({ id: 'slow-task', workstream_id: 'w-other', title: 'Competing' } as any);
		release({
			id: 'slow-task', workstream_id: 'w-other', team_id: 'tm', number: 9, key: 'OSL-9', title: 'fetched',
			status: 'todo', priority: null, assignee_ids: ['u1'], progress: 0, labels: [], sort_key: 1,
			created_by_id: 'u1', created_at: 0, updated_at: 0
		});
		await flush();
		expect(get(selectedTaskId)).toBe('slow-task'); // the competing open survives, not closed
		expect(get(inboxTask)?.title).toBe('Competing'); // untouched by the stale, discarded fetch
	});
});
