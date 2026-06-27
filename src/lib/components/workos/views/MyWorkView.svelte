<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { user } from '$lib/stores';
	import FilterBar from '../chrome/FilterBar.svelte';
	import Icon from '../ui/Icon.svelte';
	import { STATUS_LABEL, type Task, type MyWorkSegment } from '../lib/types';
	import { applyFilters } from '../lib/filters';
	import { bucketByDueDate, BUCKET_ORDER, BUCKET_LABEL } from '../lib/buckets';
	import { myTasks, myWorkFilter, loadMyWork, teardownMyWork, openTask, displayName, initials } from '../lib/store';

	let segment: MyWorkSegment = 'all';
	const SEGMENTS: { k: MyWorkSegment; label: string }[] = [
		{ k: 'all', label: 'All' }, { k: 'assigned', label: 'Assigned' }, { k: 'created', label: 'Created' }
	];

	onMount(() => { void loadMyWork(); });
	onDestroy(() => teardownMyWork());

	$: uid = $user?.id ?? '';
	function inSegment(t: Task): boolean {
		if (segment === 'assigned') return (t.assignee_ids ?? []).includes(uid);
		if (segment === 'created') return t.created_by_id === uid;
		return true;
	}
	// My Work shows open work; the Status facet can re-include done/canceled.
	$: statusFilterActive = $myWorkFilter.statuses.length > 0;
	$: visible = applyFilters(
		$myTasks.filter((t) => inSegment(t) && (statusFilterActive || (t.status !== 'done' && t.status !== 'canceled'))),
		$myWorkFilter
	);
	$: buckets = bucketByDueDate(visible, Date.now());
	const fmt = (ms: number | null | undefined) => (ms == null ? '' : new Date(ms).toLocaleDateString());
</script>

<div class="h-full flex flex-col min-h-0">
	<div class="flex-none flex items-center gap-2 px-4 pt-4">
		<h1 class="text-lg font-semibold">My Work</h1>
		<div class="flex-1"></div>
		<div class="inline-flex rounded-lg border border-gray-200 dark:border-gray-800 p-0.5 text-xs">
			{#each SEGMENTS as s (s.k)}
				<button class="px-3 py-1 rounded-md" class:bg-accent={segment === s.k} onclick={() => (segment = s.k)}>{s.label}</button>
			{/each}
		</div>
	</div>
	<FilterBar filter={myWorkFilter} showAssignee={false} />

	<div class="flex-1 overflow-auto p-4 bg-white dark:bg-gray-950">
		{#if !visible.length}
			<div class="h-full flex flex-col items-center justify-center gap-2 text-center text-gray-400">
				<Icon name="check" size={28} />
				<div class="text-sm">Nothing on your plate yet</div>
			</div>
		{:else}
			{#each BUCKET_ORDER as bucket (bucket)}
				{#if buckets[bucket].length}
					<div class="mb-5">
						<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-2">{BUCKET_LABEL[bucket]} · {buckets[bucket].length}</div>
						<div class="flex flex-col divide-y divide-gray-100 dark:divide-gray-900 rounded-lg border border-gray-200 dark:border-gray-800">
							{#each buckets[bucket] as t (t.id)}
								<button class="flex items-center gap-3 px-3 py-2 text-left hover:bg-gray-50 dark:hover:bg-gray-900" onclick={() => openTask(t.id)}>
									<span class="text-[11px] text-gray-400 w-16 flex-none">{t.key}</span>
									<span class="flex-1 truncate text-sm">{t.title}</span>
									<span class="text-[11px] text-gray-400">{STATUS_LABEL[t.status]}</span>
									{#if t.due_date}<span class="text-[11px] text-gray-400 w-24 text-right">{fmt(t.due_date)}</span>{/if}
									<span class="flex -space-x-1.5">
										{#each (t.assignee_ids ?? []).slice(0, 3) as a (a)}
											<span class="w-6 h-6 rounded-full bg-gray-200 dark:bg-gray-700 text-[10px] flex items-center justify-center border border-white dark:border-gray-950" title={displayName(a)}>{initials(a)}</span>
										{/each}
									</span>
								</button>
							{/each}
						</div>
					</div>
				{/if}
			{/each}
		{/if}
	</div>
</div>
