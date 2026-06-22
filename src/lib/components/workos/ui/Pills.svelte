<script lang="ts">
	import type { TaskPriority, TaskStatus, Label } from '../lib/types';
	export let priority: TaskPriority | null | undefined = undefined;
	export let status: TaskStatus | undefined = undefined;
	export let label: Label | undefined = undefined;

	const PRIORITY_COLOR: Record<string, string> = {
		urgent: '#dc2626', high: '#ea580c', medium: '#ca8a04', low: '#6b7280'
	};
	const STATUS_COLOR: Record<string, string> = {
		backlog: '#9ca3af', todo: '#6b7280', in_progress: '#2563eb',
		in_review: '#7c3aed', done: '#16a34a', canceled: '#9ca3af'
	};
</script>

{#if priority !== undefined && priority !== null}
	<span class="inline-flex items-center gap-1 text-[11px]" style="color:{PRIORITY_COLOR[priority]}">
		<span class="w-2 h-2 rounded-full" style="background:{PRIORITY_COLOR[priority]}"></span>{priority}
	</span>
{/if}
{#if status}
	<span class="w-2.5 h-2.5 rounded-full inline-block" style="background:{STATUS_COLOR[status]}"></span>
{/if}
{#if label}
	<span class="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800">
		<span class="w-2 h-2 rounded-full" style="background:{label.color}"></span>{label.name}
	</span>
{/if}
