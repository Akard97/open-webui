// Store <-> URL wiring for WorkOS deep linking. The ONLY place that knows the
// URL exists: views/sidebar keep calling selectWorkstream/openTask/view.set,
// and this module mirrors those stores into `?view=...&ws=...&task=...` (and back).
//
// Two one-way flows with a loop guard between them:
//   stores -> URL  (scheduleWrite: push on view/ws change, replace on task)
//   URL -> stores  (applyUrl: initial hydrate + Back/Forward via native popstate)
import { get } from 'svelte/store';
import { browser } from '$app/environment';
import { pushState, replaceState } from '$app/navigation';

import { toast } from 'svelte-sonner';
import { user } from '$lib/stores';
import {
	view, currentTeamId, currentWorkstreamId, selectedTaskId,
	workspaces, workstreams,
	selectTeam, selectWorkstream, openTaskById, closeTask
} from './store';
import { buildQuery, parseQuery, decideOp, WORKSTREAM_VIEWS, type NavState } from './urlState';
import { canUseAdmin } from './roles';

const BASE = '/workos';

let prevState: NavState | null = null; // baseline for decideOp; null = not initialized
let lastWritten: string | null = null; // canonical search we last put in the address bar
let applying = false; // URL->store application in progress: suppress echo writes
let writeQueued = false;
let pendingUrl: URL | null = null; // navigation that arrived while applying was true; latest wins
let epoch = 0; // bumped by destroyUrlSync; lets an in-flight applyUrl detect its session ended
let unsubs: Array<() => void> = [];

function currentNavState(): NavState {
	const v = get(view);
	return {
		view: v,
		// A selected workstream is real state even on global views -- but it is
		// not part of THEIR address. buildQuery would drop it anyway; nulling it
		// here keeps decideOp from seeing a phantom ws change.
		ws: WORKSTREAM_VIEWS.has(v) ? get(currentWorkstreamId) : null,
		task: get(selectedTaskId)
	};
}

// Stores -> URL. Coalesced to a microtask so a compound transition (e.g.
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

// URL -> stores. Shared by the initial hydrate and Back/Forward. Every step
// goes through the existing store functions so room ref-counting and the
// "user moved on" guards apply unchanged. Falls back without blank screens:
// bad ws -> My Work, bad task -> param dropped. Ends by canonicalizing the
// address bar when it drifted from what actually got applied.
//
// Cancellation: `epoch` is bumped by destroyUrlSync() (route left). This
// call's `myEpoch` snapshot lets it notice, after every await, that its
// session ended -- and stop touching the address bar / toasting on whatever
// route the user is on now. It can't unwind a store mutation an awaited call
// already committed (e.g. openTaskById opening the drawer for a task nobody
// is looking at anymore), so those specific cases are undone explicitly.
async function applyUrl(params: URLSearchParams, rawSearch: string): Promise<void> {
	const myEpoch = epoch;
	applying = true;
	try {
		let { view: v, ws, task } = parseQuery(params);

		// UI-cosmetic route guard: a stale/hand-edited ?view=admin for a
		// non-admin session must not survive into history. The server still
		// gates every admin action -- this only keeps the address bar honest,
		// and doesn't depend on the (scheduler-timed) reactive guard in
		// WorkOSApp to clean it up before it gets written anywhere.
		if (v === 'admin' && !canUseAdmin(get(user))) v = 'mywork';

		// Apply the view BEFORE the (possibly slow) workstream switch below:
		// otherwise the view stays 'mywork' for the whole listTasks window,
		// so MyWorkView mounts (loadMyWork + loadNotifications + per-workstream
		// room joins) only to unmount moments later -- the exact churn the
		// bootstrap default-select rule exists to avoid. BoardView renders an
		// empty board harmlessly while tasks load.
		if (get(view) !== v) view.set(v);

		if (ws && ws !== get(currentWorkstreamId)) {
			const stream = get(workstreams).find((s) => s.id === ws);
			const parent = stream ? get(workspaces).find((w) => w.id === stream.workspace_id) : undefined;
			if (stream && parent) {
				// URL wins over the localStorage team when they disagree -- link
				// sharing is the point (spec: team conflict rule).
				if (get(currentTeamId) !== parent.team_id) await selectTeam(parent.team_id);
				if (epoch !== myEpoch) return; // route left while awaiting
				await selectWorkstream(ws);
				if (epoch !== myEpoch) return;
			} else {
				// Deleted, no access (bootstrap is server-trimmed), or garbage --
				// indistinguishable by design, one fallback for all three.
				toast.error('Workstream not available');
				v = 'mywork';
				ws = null;
				task = null;
				if (get(view) !== v) view.set(v);
			}
		}

		const openId = get(selectedTaskId);
		if (task && task !== openId) {
			const result = await openTaskById(task);
			if (epoch !== myEpoch) {
				// The route was left while this fetch was in flight (epoch only
				// tracks destroyUrlSync -- a same-session navigation instead
				// queues into pendingUrl and never reaches this stale branch).
				// Only undo when THIS call is the one that actually committed
				// the open: 'superseded' means a DIFFERENT call (a newer
				// session's open, or a manual click) already owns whatever is
				// selected now -- id equality with `task` is not proof it was
				// THIS call, since another call can legitimately open the very
				// same id first. Closing on id equality alone would wipe that
				// other call's legitimate drawer instead of this dead one's.
				if (result === 'opened') closeTask();
				return;
			}
			if (result === 'gone') {
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
		// A stale call's finally must not clobber a newer session's in-flight
		// state (applying/pendingUrl belong to whichever call is CURRENT).
		if (epoch === myEpoch) {
			applying = false;
			// A navigation landed while this one was still in flight and got
			// stashed below -- apply the latest one now. Skip it if it turns out
			// to already match what we just wrote (a self-echo racing in).
			if (pendingUrl) {
				const next = pendingUrl;
				pendingUrl = null;
				if (next.search !== lastWritten) void applyUrl(next.searchParams, next.search);
			}
		}
	}
}

/**
 * True when the current URL resolves to a `ws` param -- WorkOSApp uses this
 * to skip bootstrap's default workstream selection so a deep-linked load
 * does exactly one selectWorkstream call (spec: default-selection
 * interplay). Parsed through parseQuery (not a raw has('ws')) so a param
 * hydrate would drop anyway -- e.g. ?view=inbox&ws=w1, where ws isn't a
 * workstream-view param -- doesn't also cause bootstrap to skip its default.
 */
export function urlHasWorkstream(): boolean {
	return browser && !!parseQuery(new URLSearchParams(window.location.search)).ws;
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
	// Anything that moved store state between hydrate and init drifts the
	// address bar (the ?view=admin case is now caught at parse time inside
	// applyUrl itself, but this stays as a general safety net); reconcile
	// once so lastWritten always matches reality.
	const q = buildQuery(prevState);
	if (lastWritten !== q) {
		lastWritten = q;
		replaceState(`${BASE}${q}`, {});
	}
	unsubs.push(view.subscribe(scheduleWrite));
	unsubs.push(currentWorkstreamId.subscribe(scheduleWrite));
	unsubs.push(selectedTaskId.subscribe(scheduleWrite));
	// Back/Forward: native popstate, NOT the $app/stores page store. That
	// legacy store does not track shallow-routing URLs (verified live on Kit
	// 2.59: after our pushState it emits with the PREVIOUS url), so an echo
	// comparison against it misreads every self-write as an external
	// navigation and re-applies the stale URL -- reverting the user's click.
	// popstate has neither problem: programmatic pushState/replaceState never
	// fire it, so it only reports genuine history traversal, with
	// window.location already updated.
	const onPop = () => {
		if (!window.location.pathname.endsWith(BASE)) return;
		const search = window.location.search;
		// Safety net (popstate should never echo our own writes): '' for no
		// params and '?...' otherwise -- exactly buildQuery's output.
		if (search === lastWritten) return;
		if (applying) {
			// A navigation arrived while a previous one is still being applied
			// (e.g. Back/Forward mashed during a slow deep-link fetch). Don't
			// drop it -- stash it and apply it once the current one settles;
			// only the latest matters, so this overwrites any earlier stash.
			pendingUrl = new URL(window.location.href);
			return;
		}
		void applyUrl(new URLSearchParams(search), search);
	};
	window.addEventListener('popstate', onPop);
	unsubs.push(() => window.removeEventListener('popstate', onPop));
}

export function destroyUrlSync(): void {
	for (const u of unsubs) u();
	unsubs = [];
	prevState = null;
	lastWritten = null;
	applying = false;
	writeQueued = false;
	pendingUrl = null;
	epoch++; // any applyUrl still in flight notices its session ended
}
