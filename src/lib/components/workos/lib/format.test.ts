import { describe, it, expect } from 'vitest';
import { formatDueDate, isOverdue } from './format';

describe('formatDueDate', () => {
	it('shows date only at local midnight', () => {
		const ts = new Date(2026, 5, 23, 0, 0).getTime();
		const out = formatDueDate(ts);
		expect(out).toContain('Jun');
		expect(out).toContain('23');
		expect(out).not.toContain('·');
	});
	it('includes a time when the timestamp carries one', () => {
		const ts = new Date(2026, 5, 23, 9, 30).getTime();
		expect(formatDueDate(ts)).toContain('·');
	});
});

describe('isOverdue', () => {
	const now = new Date(2026, 5, 23, 12, 0).getTime();
	it('false when no due date', () => {
		expect(isOverdue(null, 'todo', now)).toBe(false);
		expect(isOverdue(undefined, 'todo', now)).toBe(false);
	});
	it('true when past due and not finished', () => {
		expect(isOverdue(now - 1000, 'in_progress', now)).toBe(true);
	});
	it('false when due in the future', () => {
		expect(isOverdue(now + 1000, 'todo', now)).toBe(false);
	});
	it('false when done or canceled even if past due', () => {
		expect(isOverdue(now - 1000, 'done', now)).toBe(false);
		expect(isOverdue(now - 1000, 'canceled', now)).toBe(false);
	});
});
