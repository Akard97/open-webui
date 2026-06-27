<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import TaskRow from './TaskRow.svelte';
	import type { Task } from '../../lib/types';
	import { bucketByDueDate, BUCKET_ORDER, BUCKET_LABEL } from '../../lib/buckets';
	import { needsAttention } from '../../lib/stats';
	export let tasks: Task[];
	export let now: number;

	$: attention = needsAttention(tasks, now);
	$: buckets = bucketByDueDate(tasks, now);
</script>

{#if !tasks.length}
	<div class="h-full flex flex-col items-center justify-center gap-2 text-center text-gray-400 py-16">
		<Icon name="check" size={28} />
		<div class="text-sm">Nothing on your plate yet</div>
	</div>
{:else}
	{#if attention.length}
		<div class="mb-5">
			<div class="text-[11px] uppercase tracking-wide text-primary font-semibold mb-2 px-1">Needs attention · {attention.length}</div>
			<div class="flex flex-col divide-y divide-gray-100 dark:divide-gray-900 rounded-lg border border-primary/40 bg-primary/5">
				{#each attention as t (t.id)}<TaskRow task={t} />{/each}
			</div>
		</div>
	{/if}
	{#each BUCKET_ORDER as bucket (bucket)}
		{#if buckets[bucket].length}
			<div class="mb-5" data-bucket={bucket}>
				<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-2 px-1">{BUCKET_LABEL[bucket]} · {buckets[bucket].length}</div>
				<div class="flex flex-col divide-y divide-gray-100 dark:divide-gray-900 rounded-lg border border-gray-200 dark:border-gray-800">
					{#each buckets[bucket] as t (t.id)}<TaskRow task={t} />{/each}
				</div>
			</div>
		{/if}
	{/each}
{/if}
