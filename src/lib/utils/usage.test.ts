import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('$lib/constants', () => ({ WEBUI_API_BASE_URL: '/api/v1' }));

import { initUsageTracking, track, pageEnter, routeToTool, flushNow, _resetForTests } from './usage';

const fetchMock = vi.fn(async () => ({ ok: true }));

let capturedHandler: (() => void) | undefined;
let documentStub: { addEventListener: ReturnType<typeof vi.fn>; visibilityState: string };

beforeEach(() => {
	vi.useFakeTimers();
	vi.stubGlobal('fetch', fetchMock);
	vi.stubGlobal('navigator', {});
	capturedHandler = undefined;
	documentStub = {
		addEventListener: vi.fn((_evt: string, cb: () => void) => {
			capturedHandler = cb;
		}),
		visibilityState: 'visible'
	};
	vi.stubGlobal('document', documentStub);
	vi.stubGlobal('sessionStorage', {
		store: {} as Record<string, string>,
		getItem(k: string) { return this.store[k] ?? null; },
		setItem(k: string, v: string) { this.store[k] = v; }
	});
	vi.stubGlobal('crypto', { randomUUID: () => 'uuid-1' });
	fetchMock.mockClear();
	_resetForTests();
});

describe('routeToTool', () => {
	it('maps known prefixes', () => {
		expect(routeToTool('/workos').tool).toBe('workos');
		expect(routeToTool('/admin/analytics').tool).toBe('admin');
		expect(routeToTool('/home').tool).toBe('home');
		expect(routeToTool('/').tool).toBe('chat');
		expect(routeToTool('/c/abc123').tool).toBe('chat');
		expect(routeToTool('/weird').tool).toBe('other');
	});
});

describe('tracker', () => {
	it('does nothing when disabled', () => {
		initUsageTracking('tok', false);
		track('workos.view.switch', { view: 'board' });
		flushNow();
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it('flushes at 20 queued events', () => {
		initUsageTracking('tok', true);
		for (let i = 0; i < 20; i++) track('workos.view.switch', { view: 'board' });
		expect(fetchMock).toHaveBeenCalledTimes(1);
		const body = JSON.parse(fetchMock.mock.calls[0][1].body);
		expect(body.events).toHaveLength(20);
		expect(body.events[0].session_id).toBe('uuid-1');
	});

	it('flushes on the 10s interval', () => {
		initUsageTracking('tok', true);
		track('workos.view.switch', { view: 'list' });
		expect(fetchMock).not.toHaveBeenCalled();
		vi.advanceTimersByTime(10_000);
		expect(fetchMock).toHaveBeenCalledTimes(1);
	});

	it('pageEnter emits page.view, next pageEnter emits page.leave with duration', () => {
		initUsageTracking('tok', true);
		pageEnter('/workos');
		vi.advanceTimersByTime(5_000);
		pageEnter('/home');
		flushNow();
		const events = JSON.parse(fetchMock.mock.calls[0][1].body).events;
		const names = events.map((e: { name: string }) => e.name);
		expect(names).toEqual(['page.view', 'page.leave', 'page.view']);
		const leave = events[1];
		expect(leave.properties.tool).toBe('workos');
		expect(leave.properties.duration_ms).toBeGreaterThanOrEqual(5000);
	});

	it('swallows fetch failures silently', async () => {
		fetchMock.mockRejectedValueOnce(new Error('down'));
		initUsageTracking('tok', true);
		track('workos.view.switch', { view: 'board' });
		expect(() => flushNow()).not.toThrow();
	});

	it('flushes page.leave on hidden and excludes hidden time from the next duration', () => {
		initUsageTracking('tok', true);
		pageEnter('/workos');
		vi.advanceTimersByTime(5_000);

		documentStub.visibilityState = 'hidden';
		capturedHandler?.();

		expect(fetchMock).toHaveBeenCalledTimes(1);
		const hiddenEvents = JSON.parse(fetchMock.mock.calls[0][1].body).events;
		const hiddenLeave = hiddenEvents.find((e: { name: string }) => e.name === 'page.leave');
		expect(hiddenLeave.properties.duration_ms).toBeGreaterThanOrEqual(5000);

		vi.advanceTimersByTime(60_000);
		documentStub.visibilityState = 'visible';
		capturedHandler?.();

		vi.advanceTimersByTime(3_000);
		pageEnter('/home');
		flushNow();

		const allLeaves = fetchMock.mock.calls
			.flatMap((call) => JSON.parse(call[1].body).events)
			.filter((e: { name: string }) => e.name === 'page.leave');
		const secondLeave = allLeaves[1];
		expect(secondLeave.properties.duration_ms).toBeGreaterThanOrEqual(3000);
		expect(secondLeave.properties.duration_ms).toBeLessThan(60_000);
	});
});
