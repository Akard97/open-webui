import type { TaskStatus, TaskPriority } from './types';

export const STATUS_COLOR: Record<TaskStatus, string> = {
	backlog: '#9ca3af', todo: '#6b7280', in_progress: '#00a5ba',
	in_review: '#d97706', done: '#769a4a', canceled: '#9ca3af'
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
