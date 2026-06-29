<script lang="ts">
	import { actualProgress } from '../../lib/progress';
	import type { Task } from '../../lib/types';

	export let task: Task;
	$: pct = actualProgress(task);
</script>

{#if task.status === 'in_progress'}
	<div class="flex items-center gap-2">
		<span class="flex-1 h-1.5 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
			<span class="block h-full bg-primary rounded-full" style="width:{pct}%"></span>
		</span>
		<span class="text-xs text-gray-400 tabular-nums w-7 text-right">{pct}</span>
	</div>
{:else}
	<span class="text-gray-300 dark:text-gray-600">—</span>
{/if}
