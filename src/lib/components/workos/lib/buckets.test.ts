import { describe, it, expect } from 'vitest';
import { bucketByDueDate } from './buckets';
import type { Task } from './types';

const DAY = 86_400_000;
// Fixed "now": 2024-03-06 12:00 local.
const NOW = new Date(2024, 2, 6, 12, 0, 0).getTime();
const at = (d: Date) => d.getTime();

const mk = (id: string, due: number | null): Task => ({
	id, workstream_id: 'w1', team_id: 'tm', number: 1, key: 'OSL-1', title: id,
	status: 'todo', assignee_ids: [], progress: 0, labels: [], sort_key: 1,
	created_by_id: 'u1', due_date: due, created_at: 0, updated_at: 0
});

describe('bucketByDueDate', () => {
	it('classifies each task into the right rolling bucket', () => {
		const tasks = [
			mk('overdue', at(new Date(2024, 2, 5, 9, 0))),       // yesterday
			mk('today', at(new Date(2024, 2, 6, 18, 0))),        // later today
			mk('thisWeek', NOW + 3 * DAY),                       // +3 days
			mk('later', NOW + 30 * DAY),                         // +30 days
			mk('noDate', null)
		];
		const b = bucketByDueDate(tasks, NOW);
		expect(b.overdue.map((t) => t.id)).toEqual(['overdue']);
		expect(b.today.map((t) => t.id)).toEqual(['today']);
		expect(b.thisWeek.map((t) => t.id)).toEqual(['thisWeek']);
		expect(b.later.map((t) => t.id)).toEqual(['later']);
		expect(b.noDate.map((t) => t.id)).toEqual(['noDate']);
	});
	it('the 7-day boundary is inclusive of thisWeek, exclusive into later', () => {
		const endToday = new Date(2024, 2, 6, 23, 59, 59, 999).getTime();
		const b = bucketByDueDate([mk('edge', endToday + 7 * DAY)], NOW);
		expect(b.thisWeek.map((t) => t.id)).toEqual(['edge']);
	});
});
