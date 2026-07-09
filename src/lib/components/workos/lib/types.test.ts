import { describe, expect, it } from 'vitest';
import { STATUS_LABEL, type TaskStatus } from './types';

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
