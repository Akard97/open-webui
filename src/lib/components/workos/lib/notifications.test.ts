import { describe, it, expect } from 'vitest';
import { summarizeNotification } from './notifications';
import type { Notification, NotificationType } from './types';

const mk = (type: NotificationType, data: Record<string, any> = {}): Notification => ({
	id: 'n1', user_id: 'u1', actor_id: 'u2', task_id: 't1', type, data, read: false, created_at: 0
});

describe('summarizeNotification', () => {
	it('renders a line per type with actor and task key', () => {
		const d = { actor_name: 'Mia', task_key: 'OSL-7' };
		expect(summarizeNotification(mk('assigned', d))).toBe('Mia assigned you OSL-7');
		expect(summarizeNotification(mk('mentioned', d))).toBe('Mia mentioned you in OSL-7');
		expect(summarizeNotification(mk('commented', d))).toBe('Mia commented on OSL-7');
		expect(summarizeNotification(mk('status_changed', d))).toBe('Mia changed status of OSL-7');
	});

	it('falls back gracefully when actor and key are missing', () => {
		expect(summarizeNotification(mk('assigned'))).toBe('Someone assigned you');
	});

	it('uses a generic verb for unknown types', () => {
		const n = mk('something_else' as any, { actor_name: 'Mia', task_key: 'OSL-7' });
		expect(summarizeNotification(n)).toBe('Mia updated OSL-7');
	});
});
