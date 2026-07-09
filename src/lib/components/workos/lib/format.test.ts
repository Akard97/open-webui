import { describe, it, expect } from 'vitest';
import { formatDueDate, isOverdue, formatDateLong } from './format';

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
	// Due dates are stored as UTC midnight of the picked date (DueDateCell parses
	// 'YYYY-MM-DD'); overdue flips when that day fully ends in the viewer's local
	// time — the same dueDayEndLocal boundary taskHealth uses.
	const dueJun23 = Date.UTC(2026, 5, 23);
	it('false when no due date', () => {
		const now = new Date(2026, 5, 23, 12, 0).getTime();
		expect(isOverdue(null, 'todo', now)).toBe(false);
		expect(isOverdue(undefined, 'todo', now)).toBe(false);
	});
	it('false throughout the due day, including its last millisecond', () => {
		expect(isOverdue(dueJun23, 'in_progress', new Date(2026, 5, 23, 12, 0).getTime())).toBe(false);
		expect(isOverdue(dueJun23, 'in_progress', new Date(2026, 5, 23, 23, 59, 59, 999).getTime())).toBe(false);
	});
	it('true once the due day has fully ended locally', () => {
		expect(isOverdue(dueJun23, 'in_progress', new Date(2026, 5, 24, 0, 0, 0, 0).getTime())).toBe(true);
	});
	it('false when due in the future', () => {
		expect(isOverdue(dueJun23, 'todo', new Date(2026, 5, 22, 12, 0).getTime())).toBe(false);
	});
	it('false when done or canceled even if past due', () => {
		const later = new Date(2026, 5, 30, 12, 0).getTime();
		expect(isOverdue(dueJun23, 'done', later)).toBe(false);
		expect(isOverdue(dueJun23, 'canceled', later)).toBe(false);
	});
});

describe('formatDateLong', () => {
	it('renders day month year', () => {
		const ts = new Date(2024, 2, 5).getTime(); // 5 March 2024, local
		expect(formatDateLong(ts)).toBe('5 March 2024');
	});
	it('renders a single-digit day without padding', () => {
		const ts = new Date(2024, 11, 9).getTime(); // 9 December 2024
		expect(formatDateLong(ts)).toBe('9 December 2024');
	});
});
