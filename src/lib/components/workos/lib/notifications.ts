import type { Notification } from './types';

export function summarizeNotification(n: Notification): string {
	const who = n.data?.actor_name ?? 'Someone';
	const key = n.data?.task_key ? `${n.data.task_key} ` : '';
	switch (n.type) {
		case 'assigned': return `${who} assigned you ${key}`.trim();
		case 'subtask_assigned': return `${who} assigned you a subtask on ${key}`.trim();
		case 'mentioned': return `${who} mentioned you in ${key}`.trim();
		case 'commented': return `${who} commented on ${key}`.trim();
		case 'status_changed': return `${who} changed status of ${key}`.trim();
		default: return `${who} updated ${key}`.trim();
	}
}
