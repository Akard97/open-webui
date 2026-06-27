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
	const dateLabel = new Date(now).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });

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
			activeTile = activeTile === key ? null : key;
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
	<div class="flex-none flex items-end gap-3 px-4 pt-4">
		<div>
			<div class="text-[11px] uppercase tracking-[0.14em] text-gray-400 mb-0.5">{dateLabel}</div>
			<h1 class="text-2xl font-semibold tracking-tight leading-none">My Work</h1>
		</div>
		<div class="flex-1"></div>
		<div class="inline-flex rounded-full bg-gray-100 dark:bg-gray-800 p-0.5 text-xs">
			{#each SEGMENTS as s (s.k)}
				<button
					type="button"
					class="px-3 py-1 rounded-full transition-colors {segment === s.k ? 'bg-white dark:bg-gray-950 shadow-sm font-medium text-gray-900 dark:text-gray-100' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}"
					onclick={() => (segment = s.k)}
				>{s.label}</button>
			{/each}
		</div>
		{#if creating}
			<div class="flex items-center gap-1.5">
				<select class="text-sm rounded-full border border-gray-300 dark:border-gray-700 bg-transparent px-3 py-1.5" bind:value={target}>
					{#each $workstreams as s (s.id)}<option value={s.id}>{s.name}</option>{/each}
				</select>
				<input
					class="text-sm px-3 py-1.5 rounded-full border border-gray-300 dark:border-gray-700 bg-transparent w-48"
					placeholder="Task title…"
					bind:value={newTitle}
					onkeydown={(e) => { if (e.key === 'Enter') submitNew(); if (e.key === 'Escape') { creating = false; newTitle = ''; } }}
					autofocus
				/>
			</div>
		{:else}
			<button type="button" class="text-sm px-3.5 py-1.5 rounded-full bg-primary hover:bg-primary/90 text-primary-foreground inline-flex items-center gap-1 shadow-sm" onclick={() => (creating = true)}>
				<Icon name="plus" size={15} /> New task
			</button>
		{/if}
	</div>

	<StatStrip {stats} active={activeTile} onPick={pickTile} />

	<FilterBar filter={myWorkFilter} showAssignee={false} />

	<div bind:this={scroller} class="flex-1 overflow-auto p-4 bg-gray-50 dark:bg-gray-900">
		<div class="grid grid-cols-1 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-5">
			<div class="min-w-0">
				<FocusList tasks={visible} {now} />
			</div>
			<div class="flex flex-col gap-4">
				<InsightsPanel {stats} />
				<ActivityRail />
				<QuickLaunch tasks={segmentSet} />
			</div>
		</div>
	</div>
</div>
