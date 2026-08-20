import { WEBUI_API_BASE_URL } from '$lib/constants';

export type ClientEventName = 'page.view' | 'page.leave' | 'workos.view.switch' | 'workos.search.used';

type QueuedEvent = { name: ClientEventName; properties: Record<string, unknown>; session_id: string };

const FLUSH_INTERVAL_MS = 10_000;
const FLUSH_AT = 20;
const MAX_BATCH = 50;

let queue: QueuedEvent[] = [];
let timer: ReturnType<typeof setInterval> | null = null;
let enabled = false;
let token = '';
let currentPage: { tool: string; view: string; path: string; since: number } | null = null;

const sessionId = (): string => {
	let id = sessionStorage.getItem('usageSessionId');
	if (!id) {
		id = crypto.randomUUID();
		sessionStorage.setItem('usageSessionId', id);
	}
	return id;
};

export const routeToTool = (pathname: string): { tool: string; view: string } => {
	if (pathname.startsWith('/workos')) return { tool: 'workos', view: 'workos' };
	if (pathname.startsWith('/admin')) return { tool: 'admin', view: pathname.split('/')[2] ?? 'admin' };
	if (pathname.startsWith('/home')) return { tool: 'home', view: 'home' };
	if (pathname.startsWith('/policy')) return { tool: 'policy', view: pathname.split('/')[2] ?? 'policy' };
	if (pathname.startsWith('/notes')) return { tool: 'notes', view: 'notes' };
	if (pathname === '/' || pathname.startsWith('/c/')) return { tool: 'chat', view: 'chat' };
	return { tool: 'other', view: pathname.split('/')[1] || 'root' };
};

export const track = (name: ClientEventName, properties: Record<string, unknown> = {}): void => {
	if (!enabled) return;
	queue.push({ name, properties, session_id: sessionId() });
	if (queue.length >= FLUSH_AT) flushNow();
};

export const pageEnter = (pathname: string): void => {
	if (!enabled) return;
	const now = Date.now();
	if (currentPage) {
		track('page.leave', {
			tool: currentPage.tool,
			view: currentPage.view,
			path: currentPage.path,
			duration_ms: now - currentPage.since
		});
	}
	const { tool, view } = routeToTool(pathname);
	currentPage = { tool, view, path: pathname, since: now };
	track('page.view', { tool, view, path: pathname });
};

export const flushNow = (): void => {
	if (!enabled || !queue.length) return;
	const events = queue.splice(0, MAX_BATCH);
	// keepalive lets the request survive tab close and, unlike sendBeacon,
	// carries the Authorization header.
	fetch(`${WEBUI_API_BASE_URL}/usage/events`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', authorization: `Bearer ${token}` },
		body: JSON.stringify({ events }),
		keepalive: true
	}).catch(() => {
		// fire-and-forget: drop on failure
	});
};

export const initUsageTracking = (authToken: string, isEnabled: boolean): void => {
	enabled = isEnabled;
	token = authToken;
	if (!enabled || timer) return;
	timer = setInterval(flushNow, FLUSH_INTERVAL_MS);
	document.addEventListener('visibilitychange', () => {
		if (document.visibilityState === 'hidden') {
			if (currentPage) {
				track('page.leave', {
					tool: currentPage.tool,
					view: currentPage.view,
					path: currentPage.path,
					duration_ms: Date.now() - currentPage.since
				});
			}
			flushNow();
		} else if (currentPage) {
			// Reset on return so time spent hidden never counts into the
			// next page.leave duration.
			currentPage.since = Date.now();
		}
	});
};

export const _resetForTests = (): void => {
	queue = [];
	if (timer) clearInterval(timer);
	timer = null;
	enabled = false;
	token = '';
	currentPage = null;
};
