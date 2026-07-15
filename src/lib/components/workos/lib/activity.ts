import { STATUS_LABEL, type Activity, type TaskStatus } from './types';

type NameOf = (id: string | null | undefined) => string;

/** Human-readable sentence for an activity entry. Pure: name lookup is injected. */
export function activityLabel(a: Activity, nameOf: NameOf): string {
	const who = nameOf(a.user_id);
	const d = a.data as Record<string, any>;
	const st = (v: string) => STATUS_LABEL[v as TaskStatus] ?? v;
	switch (a.type) {
		case 'status_changed':
			return `${who} changed status ${st(d.from)} → ${st(d.to)}`;
		case 'completed':
			return `${who} completed this task`;
		case 'reopened':
			return `${who} reopened this task`;
		case 'assignee_changed':
			return assigneeLabel(who, d, nameOf);
		case 'priority_changed':
			return `${who} set priority to ${d.to ?? 'none'}`;
		case 'due_changed':
			return `${who} changed the due date`;
		case 'title_changed':
			return `${who} renamed this task`;
		case 'description_changed':
			return `${who} edited the description`;
		case 'comment_added':
			return `${who} commented`;
		case 'attachment_added':
			return `${who} attached ${d.name ?? 'a file'}`;
		case 'attachment_required_changed':
			return d.to
				? `${who} made attachment required to complete`
				: `${who} removed the attachment requirement`;
		default:
			return `${who} updated this task`;
	}
}

function assigneeLabel(who: string, d: Record<string, any>, nameOf: NameOf): string {
	// New payload: {added, removed}. Legacy fallback: {from, to} single ids.
	const added: string[] = d.added ?? (d.to ? [d.to] : []);
	const removed: string[] = d.removed ?? (d.from ? [d.from] : []);
	const names = (ids: string[]) => ids.map((id) => nameOf(id)).join(', ');
	if (added.length && removed.length) {
		return `${who} assigned ${names(added)} and unassigned ${names(removed)}`;
	}
	if (added.length) return `${who} assigned ${names(added)}`;
	if (removed.length) return `${who} unassigned ${names(removed)}`;
	return `${who} updated assignees`;
}
