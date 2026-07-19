// Store <-> URL wiring for WorkOS deep linking. The ONLY place that knows the
// URL exists: views/sidebar keep calling selectWorkstream/openTask/view.set,
// and this module mirrors those stores into `?view=...&ws=...&task=...` (and back).
//
// Two one-way flows with a loop guard between them:
//   stores -> URL  (scheduleWrite: push on view/ws change, replace on task)
//   URL -> stores  (applyUrl: initial hydrate + Back/Forward via page store)
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
let applying = false; // URL->store application in progress: suppress echo writes
let writeQueued = false;
let pendingUrl: URL | null = null; // navigation that arrived while applying was true; latest wins
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
async function applyUrl(params: URLSearchParams, rawSearch: string): Promise<void> {
	applying = true;
	try {
		let { view: v, ws, task } = parseQuery(params);

		if (ws && ws !== get(currentWorkstreamId)) {
			const stream = get(workstreams).find((s) => s.id === ws);
			const parent = stream ? get(workspaces).find((w) => w.id === stream.workspace_id) : undefined;
			if (stream && parent) {
				// URL wins over the localStorage team when they disagree -- link
				// sharing is the point (spec: team conflict rule).
				if (get(currentTeamId) !== parent.team_id) await selectTeam(parent.team_id);
				await selectWorkstream(ws);
			} else {
				// Deleted, no access (bootstrap is server-trimmed), or garbage --
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
		// A navigation landed while this one was still in flight and got
		// stashed below -- apply the latest one now. Skip it if it turns out to
		// already match what we just wrote (a self-echo racing in as pending).
		if (pendingUrl) {
			const next = pendingUrl;
			pendingUrl = null;
			if (next.search !== lastWritten) void applyUrl(next.searchParams, next.search);
		}
	}
}

/**
 * True when the current URL carries a `ws` param -- WorkOSApp uses this to
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
	// against the canonical form we always write. That check runs BEFORE the
	// in-flight stash below so our own writes (including the subscribe-time
	// replay of whatever hydrateFromUrl just wrote) never get queued as a
	// pending navigation.
	unsubs.push(
		page.subscribe(($p) => {
			if (!$p.url.pathname.endsWith(BASE)) return;
			// URL.search is '' for no params and '?...' otherwise -- exactly
			// buildQuery's output, so one string comparison recognizes our
			// own writes.
			if ($p.url.search === lastWritten) return;
			if (applying) {
				// A navigation arrived while a previous one is still being applied
				// (e.g. Back/Forward mashed during a slow deep-link fetch). Don't
				// drop it -- stash it and apply it once the current one settles;
				// only the latest matters, so this overwrites any earlier stash.
				pendingUrl = $p.url;
				return;
			}
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
	pendingUrl = null;
}
