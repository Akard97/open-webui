// Pure URL <-> nav-state mapping for WorkOS deep linking. No store, DOM, or
// SvelteKit dependencies (ViewKey is a type-only import) -- the wiring that
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
 * Canonical query string ('' or '?...') for a nav state. Param order is fixed
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
