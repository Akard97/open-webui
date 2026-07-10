import { describe, it, expect } from 'vitest';
import { bucketByDueDate } from './buckets';
import type { Task } from './types';

// Fixed "now": 2024-03-06 12:00 local.
const NOW = new Date(2024, 2, 6, 12, 0, 0).getTime();

const mk = (id: string, due: number | null): Task => ({
	id, workstream_id: 'w1', team_id: 'tm', number: 1, key: 'OSL-1', title: id,
	status: 'todo', assignee_ids: [], progress: 0, labels: [], sort_key: 1,
	created_by_id: 'u1', due_date: due, created_at: 0, updated_at: 0
});

describe('bucketByDueDate', () => {
	// Due dates are stored as UTC midnight of the picked date (DueDateCell parses
	// 'YYYY-MM-DD'); the overdue/today split compares dueDayEndLocal(due) — the
	// same boundary isOverdue/taskHealth use — so buckets always agree with the
	// health chip and the red due dates shown elsewhere.
	it('classifies each task into the right rolling bucket', () => {
		const tasks = [
			mk('overdue', Date.UTC(2024, 2, 5)), // due day (Mar 5) has fully ended
			mk('today', Date.UTC(2024, 2, 6)),   // due today (Mar 6), day not yet ended
			mk('thisWeek', Date.UTC(2024, 2, 9)), // +3 days
			mk('later', Date.UTC(2024, 3, 5)),    // +30 days
			mk('noDate', null)
		];
		const b = bucketByDueDate(tasks, NOW);
		expect(b.overdue.map((t) => t.id)).toEqual(['overdue']);
		expect(b.today.map((t) => t.id)).toEqual(['today']);
		expect(b.thisWeek.map((t) => t.id)).toEqual(['thisWeek']);
		expect(b.later.map((t) => t.id)).toEqual(['later']);
		expect(b.noDate.map((t) => t.id)).toEqual(['noDate']);
	});

	it('a task due today, not yet ended, is today — not overdue — at local noon', () => {
		const dueToday = Date.UTC(2024, 2, 6);
		const b = bucketByDueDate([mk('t', dueToday)], NOW);
		expect(b.today.map((t) => t.id)).toEqual(['t']);
		expect(b.overdue).toEqual([]);
	});

	it("stays today through the due day's last local millisecond, flips to overdue on the next", () => {
		const dueToday = Date.UTC(2024, 2, 6);
		const lastMs = new Date(2024, 2, 6, 23, 59, 59, 999).getTime();
		const firstMsNext = new Date(2024, 2, 7, 0, 0, 0, 0).getTime();
		expect(bucketByDueDate([mk('t', dueToday)], lastMs).today.map((t) => t.id)).toEqual(['t']);
		expect(bucketByDueDate([mk('t', dueToday)], lastMs).overdue).toEqual([]);
		expect(bucketByDueDate([mk('t', dueToday)], firstMsNext).overdue.map((t) => t.id)).toEqual(['t']);
	});

	it('the 7-day boundary is inclusive of thisWeek, exclusive into later', () => {
		const edge = Date.UTC(2024, 2, 13); // due day ends exactly at endToday + 7d
		const pastEdge = Date.UTC(2024, 2, 14);
		const b = bucketByDueDate([mk('edge', edge), mk('past', pastEdge)], NOW);
		expect(b.thisWeek.map((t) => t.id)).toEqual(['edge']);
		expect(b.later.map((t) => t.id)).toEqual(['past']);
	});
});
