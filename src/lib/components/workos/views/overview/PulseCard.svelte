<script lang="ts">
	import { openTask, displayName, initials } from '../../lib/store';
	import { activityLabel } from '../../lib/activity';
	import { agoLabel } from '../../lib/overview';
	import type { WsActivityItem } from '../../lib/store';

	export let items: WsActivityItem[];
	export let loaded = false;
	export let error = false;
	export let now: number;

	$: shown = items.slice(0, 8);
</script>

<section class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 min-w-0">
	<h3 class="text-[13.5px] font-medium">Pulse</h3>
	<p class="text-[11px] text-gray-400 mt-0.5">Latest activity in this workstream.</p>
	{#if error}
		<div class="py-6 text-center text-sm text-gray-400">Couldn't load activity.</div>
	{:else if !loaded}
		<div class="mt-3 flex flex-col gap-2">
			{#each Array(4) as _, i (i)}<div class="h-5 rounded bg-gray-100 dark:bg-gray-800 animate-pulse"></div>{/each}
		</div>
	{:else if !shown.length}
		<div class="py-6 text-center text-sm text-gray-400">No activity yet.</div>
	{:else}
		<div class="mt-2.5 flex flex-col gap-2">
			{#each shown as a (a.id)}
				<button type="button" class="flex items-start gap-2.5 text-left w-full" onclick={() => openTask(a.task_id)}>
					<span class="w-[22px] h-[22px] rounded-full bg-brand-100 text-brand-700 dark:bg-brand-900 dark:text-brand-200 text-[10px] inline-flex items-center justify-center flex-none">{initials(a.user_id)}</span>
					<span class="min-w-0 flex-1 text-[12px] text-gray-600 dark:text-gray-300 leading-snug">
						{activityLabel(a, displayName)}
						{#if a.task_key}<span class="text-primary tabular-nums"> · {a.task_key}</span>{/if}
					</span>
					<span class="flex-none text-[11px] text-gray-400">{agoLabel(a.created_at, now)}</span>
				</button>
			{/each}
		</div>
	{/if}
</section>
