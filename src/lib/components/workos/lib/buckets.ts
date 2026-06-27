import type { Task, DueBuckets } from './types';

export const BUCKET_ORDER: (keyof DueBuckets)[] = ['overdue', 'today', 'thisWeek', 'later', 'noDate'];
export const BUCKET_LABEL: Record<keyof DueBuckets, string> = {
	overdue: 'Overdue', today: 'Today', thisWeek: 'This week', later: 'Later', noDate: 'No date'
};

export function bucketByDueDate(tasks: Task[], now: number): DueBuckets {
	const d = new Date(now);
	const startToday = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
	const endToday = startToday + 86_400_000 - 1;
	const endWeek = endToday + 7 * 86_400_000;
	const out: DueBuckets = { overdue: [], today: [], thisWeek: [], later: [], noDate: [] };
	for (const t of tasks) {
		const due = t.due_date;
		if (due == null) out.noDate.push(t);
		else if (due < startToday) out.overdue.push(t);
		else if (due <= endToday) out.today.push(t);
		else if (due <= endWeek) out.thisWeek.push(t);
		else out.later.push(t);
	}
	return out;
}
