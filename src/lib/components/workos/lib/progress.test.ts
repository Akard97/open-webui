import { describe, expect, it } from 'vitest';
import { actualProgress, plannedProgress, taskHealth } from './progress';
import type { Task } from './types';

const baseTask: Task = {
	id: 't1', workstream_id: 'w1', team_id: 'team', number: 1, key: 'OSL-1',
	title: 'Task', status: 'in_progress', progress: 20, labels: [], sort_key: 1,
	created_at: 0, updated_at: 0
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

	it('marks overdue when past due and actual is below complete', () => {
		expect(taskHealth({ ...baseTask, start_date: 0, due_date: 100, progress: 90 }, 101)).toBe('overdue');
	});

	it('marks at risk and behind from planned minus actual gap', () => {
		expect(taskHealth({ ...baseTask, start_date: 0, due_date: 100, progress: 40 }, 50)).toBe('at_risk');
		expect(taskHealth({ ...baseTask, start_date: 0, due_date: 100, progress: 20 }, 50)).toBe('behind');
	});

	it('marks on track when actual is close enough to planned', () => {
		expect(taskHealth({ ...baseTask, start_date: 0, due_date: 100, progress: 45 }, 50)).toBe('on_track');
	});
});
