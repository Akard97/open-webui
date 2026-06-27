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
	<div class="h-full flex flex-col items-center justify-center gap-3 text-center text-gray-400 py-20">
		<div class="w-12 h-12 rounded-full bg-green-50 dark:bg-green-500/10 text-green-500 flex items-center justify-center">
			<Icon name="circle-check" size={24} />
		</div>
		<div class="text-sm">Nothing on your plate yet</div>
	</div>
{:else}
	{#if attention.length}
		<div class="mb-4 rounded-xl border border-red-200 dark:border-red-500/30 bg-red-50/60 dark:bg-red-500/[0.06] px-3 pt-3 pb-1.5">
			<div class="flex items-center gap-1.5 px-1 mb-1.5 text-[11px] uppercase tracking-wide font-semibold text-red-600 dark:text-red-400">
				<Icon name="flame" size={14} /> Needs attention · {attention.length}
			</div>
			<div class="flex flex-col divide-y divide-red-100 dark:divide-red-500/15">
				{#each attention as t (t.id)}<TaskRow task={t} />{/each}
			</div>
		</div>
	{/if}
	{#each BUCKET_ORDER as bucket (bucket)}
		{#if buckets[bucket].length}
			<div class="mb-4" data-bucket={bucket}>
				<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-1.5 px-1">{BUCKET_LABEL[bucket]} · {buckets[bucket].length}</div>
				<div class="flex flex-col divide-y divide-gray-100 dark:divide-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 py-1">
					{#each buckets[bucket] as t (t.id)}<TaskRow task={t} />{/each}
				</div>
			</div>
		{/if}
	{/each}
{/if}
