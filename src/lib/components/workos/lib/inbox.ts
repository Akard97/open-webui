import type { Notification } from './types';

/** One feed row: `latest` renders; `stack` (incl. latest, newest-first) expands. */
export interface FeedEntry {
	latest: Notification;
	stack: Notification[];
}

export interface DayGroup {
	label: string;
	entries: FeedEntry[];
}

export interface InboxGroups {
	needsYou: Notification[];
	days: DayGroup[];
}

/** "Needs you" = unread mentions + assignments; read ones flow into the feed. */
export function isNeedsYou(n: Notification): boolean {
	return !n.read && (n.type === 'mentioned' || n.type === 'assigned');
}

const startOfDay = (ms: number): number => new Date(ms).setHours(0, 0, 0, 0);

export function dayLabelOf(ms: number, now: number): string {
	const diff = Math.round((startOfDay(now) - startOfDay(ms)) / 86_400_000);
	if (diff <= 0) return 'Today';
	if (diff === 1) return 'Yesterday';
	return new Date(ms).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}

/**
 * Split a newest-first notification list into the pinned needs-you set and
 * day groups; within a day, consecutive rows on the same task collapse into
 * one FeedEntry (stack). A null task_id never stacks.
 */
export function groupInbox(list: Notification[], now: number): InboxGroups {
	const needsYou: Notification[] = [];
	const days: DayGroup[] = [];
	for (const n of list) {
		if (isNeedsYou(n)) {
			needsYou.push(n);
			continue;
		}
		const label = dayLabelOf(n.created_at, now);
		let day = days[days.length - 1];
		if (!day || day.label !== label) {
			day = { label, entries: [] };
			days.push(day);
		}
		const last = day.entries[day.entries.length - 1];
		if (last && last.latest.task_id != null && last.latest.task_id === n.task_id) {
			last.stack.push(n);
		} else {
			day.entries.push({ latest: n, stack: [n] });
		}
	}
	return { needsYou, days };
}
