<script lang="ts">
	import { displayName } from '../../lib/store';
	import { STATUS_LABEL, type Activity, type TaskStatus } from '../../lib/types';

	export let activity: Activity;

	function label(a: Activity): string {
		const who = displayName(a.user_id);
		const d = a.data as Record<string, any>;
		const st = (v: string) => STATUS_LABEL[v as TaskStatus] ?? v;
		switch (a.type) {
			case 'status_changed': return `${who} changed status ${st(d.from)} → ${st(d.to)}`;
			case 'completed': return `${who} completed this task`;
			case 'reopened': return `${who} reopened this task`;
			case 'assignee_changed': return `${who} ${d.to ? `assigned ${displayName(d.to)}` : 'unassigned this'}`;
			case 'priority_changed': return `${who} set priority to ${d.to ?? 'none'}`;
			case 'due_changed': return `${who} changed the due date`;
			case 'title_changed': return `${who} renamed this task`;
			case 'description_changed': return `${who} edited the description`;
			case 'comment_added': return `${who} commented`;
			case 'attachment_added': return `${who} attached ${d.name ?? 'a file'}`;
			default: return `${who} updated this task`;
		}
	}
</script>

<div class="flex items-center gap-2 text-xs text-gray-400 py-1">
	<span class="w-1.5 h-1.5 rounded-full bg-gray-300 dark:bg-gray-600 flex-none"></span>
	<span>{label(activity)}</span>
</div>
