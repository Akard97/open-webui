<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { user } from '$lib/stores';
	import FilterBar from '../chrome/FilterBar.svelte';
	import Icon from '../ui/Icon.svelte';
	import StatStrip from './commandcenter/StatStrip.svelte';
	import InsightsPanel from './commandcenter/InsightsPanel.svelte';
	import ActivityRail from './commandcenter/ActivityRail.svelte';
	import QuickLaunch from './commandcenter/QuickLaunch.svelte';
	import FocusList from './commandcenter/FocusList.svelte';
	import { type MyWorkSegment, type TaskStatus } from '../lib/types';
	import { applyFilters } from '../lib/filters';
	import { computeStats } from '../lib/stats';
	import { myTasks, myWorkFilter, workstreams, loadMyWork, teardownMyWork, addTask } from '../lib/store';

	let segment: MyWorkSegment = 'all';
	const SEGMENTS: { k: MyWorkSegment; label: string }[] = [
		{ k: 'all', label: 'All' }, { k: 'assigned', label: 'Assigned' }, { k: 'created', label: 'Created' }
	];

	onMount(() => { void loadMyWork(); });
	onDestroy(() => teardownMyWork());

	$: uid = $user?.id ?? '';
	const now = Date.now();

	// segmentSet: segment-only — no FilterBar, no done/canceled hide. Feeds the stats.
	$: segmentSet = $myTasks.filter((t) =>
		segment === 'assigned' ? (t.assignee_ids ?? []).includes(uid)
		: segment === 'created' ? t.created_by_id === uid
		: true
	);
	$: stats = computeStats(segmentSet, now);

	// visible: the worked list set — segment + done/canceled hide + FilterBar (as before).
	$: statusFilterActive = $myWorkFilter.statuses.length > 0;
	$: visible = applyFilters(
		segmentSet.filter((t) => statusFilterActive || (t.status !== 'done' && t.status !== 'canceled')),
		$myWorkFilter
	);

	// KPI tile interaction: in-progress/done-this-week toggle a status facet; overdue/today scroll.
	let activeTile: string | null = null;
	let scroller: HTMLElement;
	function pickTile(key: string) {
		if (key === 'inProgress' || key === 'doneThisWeek') {
			const status: TaskStatus = key === 'inProgress' ? 'in_progress' : 'done';
			const on = $myWorkFilter.statuses.includes(status);
			myWorkFilter.update((f) => ({
				...f,
				statuses: on ? f.statuses.filter((s) => s !== status) : [...f.statuses, status]
			}));
			activeTile = on ? null : key;
		} else {
			const bucket = key === 'overdue' ? 'overdue' : 'today';
			scroller?.querySelector(`[data-bucket="${bucket}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
			activeTile = key;
		}
	}

	// Cross-workstream new task: pick a target workstream (default = most recently updated task's).
	let creating = false;
	let newTitle = '';
	let target = '';
	$: defaultStream = [...$myTasks].sort((a, b) => b.updated_at - a.updated_at)[0]?.workstream_id ?? $workstreams[0]?.id ?? '';
	$: if (!target) target = defaultStream;
	async function submitNew() {
		if (!newTitle.trim() || !target) return;
		await addTask(target, { title: newTitle.trim() });
		newTitle = ''; creating = false;
	}
</script>

<div class="h-full flex flex-col min-h-0">
	<div class="flex-none flex items-center gap-2 px-4 pt-4">
		<h1 class="text-lg font-semibold">My Work</h1>
		<div class="flex-1"></div>
		<div class="inline-flex rounded-lg border border-gray-200 dark:border-gray-800 p-0.5 text-xs">
			{#each SEGMENTS as s (s.k)}
				<button type="button" class="px-3 py-1 rounded-md" class:bg-accent={segment === s.k} onclick={() => (segment = s.k)}>{s.label}</button>
			{/each}
		</div>
		{#if creating}
			<div class="flex items-center gap-1.5">
				<select class="text-sm rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent px-2 py-1" bind:value={target}>
					{#each $workstreams as s (s.id)}<option value={s.id}>{s.name}</option>{/each}
				</select>
				<input
					class="text-sm px-2 py-1 rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent w-48"
					placeholder="Task title…"
					bind:value={newTitle}
					onkeydown={(e) => { if (e.key === 'Enter') submitNew(); if (e.key === 'Escape') { creating = false; newTitle = ''; } }}
					autofocus
				/>
			</div>
		{:else}
			<button type="button" class="text-sm px-3 py-1.5 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground inline-flex items-center gap-1" onclick={() => (creating = true)}>
				<Icon name="plus" size={15} /> New task
			</button>
		{/if}
	</div>

	<StatStrip {stats} active={activeTile} onPick={pickTile} />

	<FilterBar filter={myWorkFilter} showAssignee={false} />

	<div bind:this={scroller} class="flex-1 overflow-auto p-4 bg-white dark:bg-gray-950">
		<div class="grid grid-cols-1 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-4">
			<div class="min-w-0">
				<FocusList tasks={visible} {now} />
			</div>
			<div class="flex flex-col gap-3">
				<InsightsPanel {stats} />
				<ActivityRail />
				<QuickLaunch tasks={segmentSet} />
			</div>
		</div>
	</div>
</div>
