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

// Defined before the $app/navigation mock (source order == hoist order for
// vi.hoisted/vi.mock) so that mock's factory can reference it.
const pageStore = vi.hoisted(() => {
	// Deferred require: vi.hoisted runs before ESM imports are evaluated.
	const { writable } = require('svelte/store');
	return writable({ url: new URL('http://localhost/workos') });
});

vi.mock('$app/navigation', () => ({
	// Mirror real SvelteKit shallow routing: push/replaceState update the page
	// store synchronously, just like a real navigation would. Without this the
	// mocked address bar (pageStore) can drift from what urlSync just wrote,
	// making its own writes look like external navigations.
	pushState: vi.fn((url: string) => pageStore.set({ url: new URL(url, 'http://localhost') })),
	replaceState: vi.fn((url: string) => pageStore.set({ url: new URL(url, 'http://localhost') }))
}));
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

// In real SvelteKit, window.location (what hydrateFromUrl reads) and the page
// store always describe the same URL. Tests must preserve that invariant --
// otherwise the subscribe-time replay in initUrlSync legitimately looks like
// an external navigation that needs applying, rather than the state
// hydrateFromUrl just finished applying.
const hydrate = async (s: string) => {
	pageStore.set({ url: new URL(`http://localhost/workos${s}`) });
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
	pageStore.set({ url: new URL('http://localhost/workos') });
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

describe('URL → store (Back/Forward via page store)', () => {
	it('a popstate URL re-hydrates the stores', async () => {
		await hydrate('?view=board&ws=w1');
		initUrlSync();
		pageStore.set({ url: new URL('http://localhost/workos?view=inbox') });
		await flush();
		expect(get(view)).toBe('inbox');
	});

	it('closes the drawer when the restored URL has no task', async () => {
		await hydrate('?view=board&ws=w1&task=t-in-list');
		initUrlSync();
		pageStore.set({ url: new URL('http://localhost/workos?view=board&ws=w1') });
		await flush();
		expect(get(selectedTaskId)).toBeNull();
	});

	it('reflected self-written URLs cause no extra history writes (loop guard)', async () => {
		await hydrate('');
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
		await hydrate('?view=board&ws=w1');
		initUrlSync();
		pageStore.set({ url: new URL('http://localhost/c/abc123?view=inbox') });
		await flush();
		expect(get(view)).toBe('board');
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
		pageStore.set({ url: new URL('http://localhost/workos?view=board&ws=w1&task=slow-task') });
		await Promise.resolve(); // let the first applyUrl start and reach its await
		// Second navigation arrives mid-flight -- must be queued, not dropped.
		pageStore.set({ url: new URL('http://localhost/workos?view=inbox') });
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
		pageStore.set({ url: new URL('http://localhost/workos?view=board&ws=w1&task=slow-task') });
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
		pageStore.set({ url: new URL('http://localhost/workos?view=board&ws=w1&task=slow-task') });
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
