import type { Task, TaskFilter } from './types';

export function emptyFilter(): TaskFilter {
	return { statuses: [], priorities: [], labelIds: [], assigneeIds: [], text: '' };
}

const overlaps = (a: string[], b: string[]): boolean => a.some((x) => b.includes(x));

export function matchesFilter(task: Task, f: TaskFilter): boolean {
	if (f.statuses.length && !f.statuses.includes(task.status)) return false;
	if (f.priorities.length && !(task.priority && f.priorities.includes(task.priority))) return false;
	if (f.labelIds.length && !overlaps(task.labels ?? [], f.labelIds)) return false;
	if (f.assigneeIds.length && !overlaps(task.assignee_ids ?? [], f.assigneeIds)) return false;
	const text = f.text.trim().toLowerCase();
	if (text && !(`${task.title} ${task.key}`.toLowerCase().includes(text))) return false;
	return true;
}

export function applyFilters(tasks: Task[], f: TaskFilter): Task[] {
	return tasks.filter((t) => matchesFilter(t, f));
}
