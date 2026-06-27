<script lang="ts">
	import type { TaskPriority, TaskStatus, Label } from '../lib/types';
	import { STATUS_COLOR, PRIORITY_COLOR } from '../lib/colors';
	export let priority: TaskPriority | null | undefined = undefined;
	export let status: TaskStatus | undefined = undefined;
	export let label: Label | undefined = undefined;
	export let size: 'sm' | 'md' = 'sm';

	$: textSize = size === 'md' ? 'text-sm' : 'text-[11px]';
</script>

{#if priority !== undefined && priority !== null}
	<span class="inline-flex items-center gap-1 {textSize}" style="color:{PRIORITY_COLOR[priority]}">
		<span class="w-2 h-2 rounded-full" style="background:{PRIORITY_COLOR[priority]}"></span>{priority}
	</span>
{/if}
{#if status}
	<span class="w-2.5 h-2.5 rounded-full inline-block" style="background:{STATUS_COLOR[status]}"></span>
{/if}
{#if label}
	<span class="inline-flex items-center gap-1 {textSize} px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800">
		<span class="w-2 h-2 rounded-full" style="background:{label.color}"></span>{label.name}
	</span>
{/if}
