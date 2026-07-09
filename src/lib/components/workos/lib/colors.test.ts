import { describe, expect, it } from 'vitest';
import { statusShape, tint, PRIORITY_NONE, STATUS_LABEL, PRIORITY_LABEL } from './colors';
import type { TaskStatus, TaskPriority } from './types';

describe('statusShape', () => {
	it('maps each status to its board glyph shape', () => {
		expect(statusShape('backlog')).toBe('dashed');
		expect(statusShape('todo')).toBe('ring');
		expect(statusShape('in_progress')).toBe('half');
		expect(statusShape('in_review')).toBe('half');
		expect(statusShape('done')).toBe('check');
		expect(statusShape('canceled')).toBe('x');
	});
});

describe('tint', () => {
	it('defaults to a 14% color-mix tint', () => {
		expect(tint('#00a5ba')).toBe('color-mix(in srgb, #00a5ba 14%, transparent)');
	});

	it('accepts a custom percentage', () => {
		expect(tint('#dc2626', 10)).toBe('color-mix(in srgb, #dc2626 10%, transparent)');
	});
});

describe('PRIORITY_NONE', () => {
	it('is the fallback gray for "no priority"', () => {
		expect(PRIORITY_NONE).toBe('#9ca3af');
	});
});

describe('STATUS_LABEL', () => {
	it('covers every status with the exact display string', () => {
		const expected: Record<TaskStatus, string> = {
			backlog: 'Backlog',
			todo: 'Todo',
			in_progress: 'In Progress',
			in_review: 'In Review',
			done: 'Done',
			canceled: 'Canceled'
		};
		expect(STATUS_LABEL).toEqual(expected);
	});
});

describe('PRIORITY_LABEL', () => {
	it('covers every priority with the exact display string', () => {
		const expected: Record<TaskPriority, string> = {
			urgent: 'Urgent',
			high: 'High',
			medium: 'Medium',
			low: 'Low'
		};
		expect(PRIORITY_LABEL).toEqual(expected);
	});
});
