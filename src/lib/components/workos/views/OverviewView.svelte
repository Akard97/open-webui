<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import {
		tasks, currentWorkstream, workspaces, wsActivity,
		loadWorkstreamActivity, displayName
	} from '../lib/store';
	import {
		computeKpis, weeklyMomentum, completionTime, priorityPairs, statusMix,
		teamRows, attentionList, isOpen
	} from '../lib/overview';
	import KpiBand from './overview/KpiBand.svelte';
	import MomentumCard from './overview/MomentumCard.svelte';
	import DistributionCard from './overview/DistributionCard.svelte';
	import TeamTable from './overview/TeamTable.svelte';

	// Live clock so overdue/day buckets roll over without a reload (spec §2).
	let now = Date.now();
	let timer: ReturnType<typeof setInterval>;
	onMount(() => { timer = setInterval(() => (now = Date.now()), 60_000); });
	onDestroy(() => clearInterval(timer));

	// Momentum window (weeks); KPI tiles stay on rolling 7-day windows by design.
	let weeks: 4 | 6 | 12 = 6;

	$: ws = $currentWorkstream;
	$: parentWorkspace = ws ? $workspaces.find((w) => w.id === ws.workspace_id) : null;

	let loadedFor: string | null = null;
	$: if (ws && loadedFor !== ws.id) { loadedFor = ws.id; void loadWorkstreamActivity(ws.id); }

	$: kpis = computeKpis($tasks, now);
	$: bins = weeklyMomentum($tasks, now, weeks);
	$: completion = completionTime($tasks, now, weeks);
	$: pairs = priorityPairs($tasks);
	$: mix = statusMix($tasks);
	$: rows = teamRows($tasks, now, displayName);
	$: attention = attentionList($tasks, now);
	$: peopleCount = new Set($tasks.filter(isOpen).flatMap((t) => t.assignee_ids ?? [])).size;
</script>

<div class="h-full overflow-auto bg-gray-50 dark:bg-gray-900">
	<div class="max-w-[1240px] mx-auto p-4 flex flex-col gap-3">
		{#if !mix.total}
			<div class="h-64 flex flex-col items-center justify-center gap-2 text-center">
				<div class="text-lg font-medium">No tasks here yet</div>
				<div class="text-sm text-gray-500">Add tasks on the board and this overview fills itself in.</div>
			</div>
		{:else}
			<KpiBand
				{kpis} {weeks} onWeeks={(w) => (weeks = w)}
				workspaceName={parentWorkspace?.name ?? ''} workstreamName={ws?.name ?? ''}
				taskCount={mix.total} {peopleCount}
			/>
			<div class="grid grid-cols-1 xl:grid-cols-[1.6fr_1fr] gap-3 items-start">
				<MomentumCard {bins} {completion} />
				<DistributionCard {pairs} {mix} daily={$wsActivity.daily} loaded={$wsActivity.loaded} error={$wsActivity.error} />
			</div>
			<TeamTable {rows} />
			<div class="grid grid-cols-1 xl:grid-cols-[1.35fr_1fr] gap-3 items-start">
				<!-- Task 14 mounts AttentionList + PulseCard -->
				<div data-slot="attention"></div>
				<div data-slot="pulse"></div>
			</div>
		{/if}
	</div>
</div>
