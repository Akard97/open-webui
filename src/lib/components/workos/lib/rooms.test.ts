import { describe, it, expect, vi } from 'vitest';
import { RoomRefs } from './rooms';

describe('RoomRefs', () => {
	it('subscribes once on first enter, no re-emit on second enter', () => {
		const sub = vi.fn(), unsub = vi.fn();
		const r = new RoomRefs(sub, unsub);
		r.enter('stream:a');
		r.enter('stream:a');
		expect(sub).toHaveBeenCalledTimes(1);
	});
	it('unsubscribes only when the last reference leaves', () => {
		const sub = vi.fn(), unsub = vi.fn();
		const r = new RoomRefs(sub, unsub);
		r.enter('stream:a');
		r.enter('stream:a');
		r.leave('stream:a');
		expect(unsub).not.toHaveBeenCalled(); // board still holds it
		r.leave('stream:a');
		expect(unsub).toHaveBeenCalledTimes(1);
	});
	it('leave on an unknown key is a no-op', () => {
		const sub = vi.fn(), unsub = vi.fn();
		const r = new RoomRefs(sub, unsub);
		r.leave('stream:ghost');
		expect(unsub).not.toHaveBeenCalled();
	});
	it('keys() lists currently-held rooms', () => {
		const r = new RoomRefs(vi.fn(), vi.fn());
		r.enter('team:t1');
		r.enter('stream:a');
		expect(r.keys().sort()).toEqual(['stream:a', 'team:t1']);
	});
});
