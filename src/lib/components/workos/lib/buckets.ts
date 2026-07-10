import type { Task, DueBuckets } from './types';
import { dueDayEndLocal } from './progress';

export const BUCKET_ORDER: (keyof DueBuckets)[] = ['overdue', 'today', 'thisWeek', 'later', 'noDate'];
export const BUCKET_LABEL: Record<keyof DueBuckets, string> = {
	overdue: 'Overdue', today: 'Today', thisWeek: 'This week', later: 'Later', noDate: 'No date'
};

// Status-agnostic: callers pre-filter (stats.ts relies on pure date classification
// across all statuses). Bucketing compares dueDayEndLocal(due) — the due day's end
// in the viewer's local time — the same boundary isOverdue/taskHealth use, so a
// task's bucket always agrees with its health chip and red due date elsewhere.
export function bucketByDueDate(tasks: Task[], now: number): DueBuckets {
	const d = new Date(now);
	const endToday = new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23, 59, 59, 999).getTime();
	const endWeek = endToday + 7 * 86_400_000;
	const out: DueBuckets = { overdue: [], today: [], thisWeek: [], later: [], noDate: [] };
	for (const t of tasks) {
		const due = t.due_date;
		if (due == null) { out.noDate.push(t); continue; }
		const end = dueDayEndLocal(due);
		if (now > end) out.overdue.push(t);
		else if (end <= endToday) out.today.push(t);
		else if (end <= endWeek) out.thisWeek.push(t);
		else out.later.push(t);
	}
	return out;
}
