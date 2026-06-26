import type { Task } from './types';

export type TaskHealth = 'on_track' | 'at_risk' | 'behind' | 'overdue';

function clampPercent(value: number): number {
	return Math.max(0, Math.min(100, Math.round(value)));
}

export function plannedProgress(
	startDate: number | null | undefined,
	dueDate: number | null | undefined,
	now: number
): number | null {
	if (startDate == null || dueDate == null) return null;
	if (dueDate <= startDate) return now >= dueDate ? 100 : 0;
	if (now <= startDate) return 0;
	if (now >= dueDate) return 100;
	return clampPercent(((now - startDate) / (dueDate - startDate)) * 100);
}

export function actualProgress(task: Pick<Task, 'progress' | 'subtask_total' | 'subtask_completed'>): number {
	const total = task.subtask_total ?? 0;
	const completed = task.subtask_completed ?? 0;
	if (total > 0) return clampPercent((completed / total) * 100);
	return clampPercent(task.progress ?? 0);
}

export function taskHealth(task: Task, now: number): TaskHealth | null {
	if (task.status === 'done' || task.status === 'canceled') return null;
	const planned = plannedProgress(task.start_date, task.due_date, now);
	if (planned == null) return null;
	const actual = actualProgress(task);
	if (task.due_date != null && now > task.due_date && actual < 100) return 'overdue';
	const gap = planned - actual;
	if (gap >= 25) return 'behind';
	if (gap >= 10) return 'at_risk';
	return 'on_track';
}

export const HEALTH_LABEL: Record<TaskHealth, string> = {
	on_track: 'On track',
	at_risk: 'At risk',
	behind: 'Behind',
	overdue: 'Overdue'
};

export function pointerToPercent(
	clientX: number,
	rect: { left: number; width: number }
): number {
	if (rect.width <= 0) return 0;
	const fraction = (clientX - rect.left) / rect.width;
	return Math.max(0, Math.min(100, Math.round(fraction * 100)));
}

// Parse a progress value typed into the percent input. The input is bound to a
// `type="number"` field, so the raw value may already be a number (or null when
// empty) — accept string, number, null, or undefined. Returns an integer clamped
// to 0-100, or null when the input is empty/non-numeric (caller should revert).
export function parsePercentInput(raw: unknown): number | null {
	const text = String(raw ?? '').trim();
	if (text === '') return null;
	const n = Number(text);
	if (Number.isNaN(n)) return null;
	return clampPercent(n);
}
