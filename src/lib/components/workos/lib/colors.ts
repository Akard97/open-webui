import type { TaskStatus, TaskPriority } from './types';

export const STATUS_COLOR: Record<TaskStatus, string> = {
	backlog: '#9ca3af', todo: '#6b7280', in_progress: '#00a5ba',
	in_review: '#d97706', done: '#769a4a', canceled: '#9ca3af'
};

export const PRIORITY_COLOR: Record<TaskPriority, string> = {
	urgent: '#dc2626', high: '#ea580c', medium: '#ca8a04', low: '#6b7280'
};
