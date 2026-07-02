import { describe, expect, it } from 'vitest';
import {
	actualProgress,
	plannedProgress,
	taskHealth,
	pointerToPercent,
	parsePercentInput,
	dueDayStartLocal,
	dueDayEndLocal
} from './progress';
import type { Task } from './types';

const baseTask: Task = {
	id: 't1', workstream_id: 'w1', team_id: 'team', number: 1, key: 'OSL-1',
	title: 'Task', status: 'in_progress', progress: 20, labels: [], sort_key: 1,
	assignee_ids: [], created_at: 0, updated_at: 0
};

describe('plannedProgress', () => {
	it('returns null without both dates', () => {
		expect(plannedProgress(null, 100, 50)).toBeNull();
		expect(plannedProgress(0, null, 50)).toBeNull();
	});

	it('clamps before start and after due date', () => {
		expect(plannedProgress(100, 200, 50)).toBe(0);
		expect(plannedProgress(100, 200, 250)).toBe(100);
	});

	it('calculates percent elapsed between start and due', () => {
		expect(plannedProgress(100, 200, 150)).toBe(50);
	});
});

describe('actualProgress', () => {
	it('uses manual task progress when there are no subtasks', () => {
		expect(actualProgress({ ...baseTask, progress: 35, subtask_total: 0, subtask_completed: 0 })).toBe(35);
	});

	it('uses completed subtask ratio when subtasks exist', () => {
		expect(actualProgress({ ...baseTask, progress: 10, subtask_total: 4, subtask_completed: 3 })).toBe(75);
	});
});

describe('taskHealth', () => {
	it('returns null when schedule dates are missing', () => {
		expect(taskHealth({ ...baseTask, start_date: null, due_date: null }, 150)).toBeNull();
	});

	it('marks overdue when past due even without a start date', () => {
		expect(taskHealth({ ...baseTask, start_date: null, due_date: 100, progress: 90 }, dueDayEndLocal(100) + 1)).toBe('overdue');
	});

	it('marks overdue when past due even at 100% progress (status, not progress, completes a task)', () => {
		expect(taskHealth({ ...baseTask, start_date: null, due_date: 100, progress: 100 }, dueDayEndLocal(100) + 1)).toBe('overdue');
	});

	it('marks overdue when past due and actual is below complete', () => {
		expect(taskHealth({ ...baseTask, start_date: 0, due_date: 100, progress: 90 }, dueDayEndLocal(100) + 1)).toBe('overdue');
	});

	it('marks at risk and behind from planned minus actual gap', () => {
		expect(taskHealth({ ...baseTask, start_date: 0, due_date: 100, progress: 40 }, 50)).toBe('at_risk');
		expect(taskHealth({ ...baseTask, start_date: 0, due_date: 100, progress: 20 }, 50)).toBe('behind');
	});

	it('marks on track when actual is close enough to planned', () => {
		expect(taskHealth({ ...baseTask, start_date: 0, due_date: 100, progress: 45 }, 50)).toBe('on_track');
	});
});

describe('due-day helpers', () => {
	// Due dates are stored as UTC midnight of the picked date (DueDateCell parses 'YYYY-MM-DD').
	const dueJun15 = Date.UTC(2026, 5, 15); // 2026-06-15T00:00Z

	it('dueDayStartLocal maps the UTC date to local midnight', () => {
		expect(dueDayStartLocal(dueJun15)).toBe(new Date(2026, 5, 15).getTime());
	});

	it('dueDayEndLocal maps the UTC date to local 23:59:59.999', () => {
		expect(dueDayEndLocal(dueJun15)).toBe(new Date(2026, 5, 15, 23, 59, 59, 999).getTime());
	});
});

describe('taskHealth overdue boundary (due day counts as not-overdue)', () => {
	const dueJun15 = Date.UTC(2026, 5, 15);
	const base = { status: 'todo', progress: 0, labels: [], assignee_ids: [] } as any;

	it('is not overdue during the due day', () => {
		const now = new Date(2026, 5, 15, 9, 0).getTime();
		expect(taskHealth({ ...base, due_date: dueJun15, start_date: null }, now)).not.toBe('overdue');
	});

	it('is overdue one ms after the due day ends', () => {
		const now = new Date(2026, 5, 15, 23, 59, 59, 999).getTime() + 1;
		expect(taskHealth({ ...base, due_date: dueJun15, start_date: null }, now)).toBe('overdue');
	});
});

describe('pointerToPercent', () => {
	const rect = { left: 100, width: 200 }; // spans clientX 100..300

	it('returns 0 at the left edge', () => {
		expect(pointerToPercent(100, rect)).toBe(0);
	});

	it('returns 100 at the right edge', () => {
		expect(pointerToPercent(300, rect)).toBe(100);
	});

	it('returns 50 at the midpoint', () => {
		expect(pointerToPercent(200, rect)).toBe(50);
	});

	it('clamps to 0 left of the bar', () => {
		expect(pointerToPercent(40, rect)).toBe(0);
	});

	it('clamps to 100 right of the bar', () => {
		expect(pointerToPercent(999, rect)).toBe(100);
	});

	it('rounds to the nearest integer', () => {
		expect(pointerToPercent(101, rect)).toBe(1); // 0.5% -> rounds to 1 (Math.round)
		expect(pointerToPercent(102, { left: 0, width: 300 })).toBe(34); // 102/300=0.34
	});

	it('returns 0 for a zero-width rect', () => {
		expect(pointerToPercent(50, { left: 0, width: 0 })).toBe(0);
	});
});

describe('parsePercentInput', () => {
	it('parses a numeric string', () => {
		expect(parsePercentInput('50')).toBe(50);
	});

	it('trims surrounding whitespace', () => {
		expect(parsePercentInput('  80 ')).toBe(80);
	});

	it('accepts a number (number-input bindings coerce to number)', () => {
		expect(parsePercentInput(73)).toBe(73);
	});

	it('clamps above 100 and below 0', () => {
		expect(parsePercentInput('150')).toBe(100);
		expect(parsePercentInput('-5')).toBe(0);
	});

	it('rounds fractional input', () => {
		expect(parsePercentInput('50.7')).toBe(51);
		expect(parsePercentInput('50.4')).toBe(50);
	});

	it('returns null for empty, whitespace, or non-numeric input', () => {
		expect(parsePercentInput('')).toBeNull();
		expect(parsePercentInput('   ')).toBeNull();
		expect(parsePercentInput('abc')).toBeNull();
	});

	it('returns null for null/undefined (empty number input)', () => {
		expect(parsePercentInput(null)).toBeNull();
		expect(parsePercentInput(undefined)).toBeNull();
	});
});
