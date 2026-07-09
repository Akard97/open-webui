import type { TaskStatus, TaskPriority } from './types';

export const STATUS_COLOR: Record<TaskStatus, string> = {
	backlog: '#9ca3af', todo: '#6b7280', in_progress: '#00a5ba' /* Osool 3125 C */,
	in_review: '#d97706', done: '#769a4a' /* Osool 576 C */, canceled: '#9ca3af'
};

export const PRIORITY_COLOR: Record<TaskPriority, string> = {
	urgent: '#dc2626', high: '#ea580c', medium: '#ca8a04', low: '#6b7280'
};

export type StatusShape = 'dashed' | 'ring' | 'half' | 'check' | 'x';

// State-shaped glyph per status, matching the Board's StatusDot rendering.
export const STATUS_SHAPE: Record<TaskStatus, StatusShape> = {
	backlog: 'dashed', todo: 'ring', in_progress: 'half',
	in_review: 'half', done: 'check', canceled: 'x'
};

export function statusShape(s: TaskStatus): StatusShape {
	return STATUS_SHAPE[s];
}

/** Fallback color for "no priority" — kills the #cbd5e1/#9ca3af/gray-300 drift. */
export const PRIORITY_NONE = '#9ca3af';

/** One tint recipe for all status/priority chip backgrounds (replaces bespoke `{hex}24` / `{hex}1f` alpha suffixes). */
export function tint(color: string, pct = 14): string {
	return `color-mix(in srgb, ${color} ${pct}%, transparent)`;
}

export const STATUS_LABEL: Record<TaskStatus, string> = {
	backlog: 'Backlog', todo: 'Todo', in_progress: 'In Progress',
	in_review: 'In Review', done: 'Done', canceled: 'Canceled'
};

export const PRIORITY_LABEL: Record<TaskPriority, string> = {
	urgent: 'Urgent', high: 'High', medium: 'Medium', low: 'Low'
};
