<script lang="ts">
	import { displayName, initials } from '../../lib/store';
	import type { TeamRow, MemberHealth } from '../../lib/overview';

	export let rows: TeamRow[];

	const HEALTH_PILL: Record<MemberHealth, { label: string; cls: string }> = {
		on_track: { label: 'On track', cls: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' },
		watch: { label: 'Watch', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300' },
		needs_support: { label: 'Needs support', cls: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300' }
	};
	const HEALTH_RULE =
		'Needs support: 2+ tasks overdue or behind · Watch: 1 overdue/behind or 2+ at risk · On track: otherwise';
	const GRID = 'grid-template-columns:minmax(150px,1.4fr) repeat(4,minmax(58px,.7fr)) minmax(110px,1.1fr) minmax(104px,.9fr)';
	// Deterministic avatar tint per user id (same trick as elsewhere: hash → palette).
	const AVATAR = ['#007a8a', '#769a4a', '#d97706', '#7c3aed', '#db2777', '#0ea5e9'];
	function avatarColor(id: string): string {
		let h = 0;
		for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
		return AVATAR[h % AVATAR.length];
	}
</script>

<section class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 min-w-0">
	<h3 class="text-[13.5px] font-medium">Team performance</h3>
	<p class="text-[11px] text-gray-400 mt-0.5">
		Assignments and workload across this workstream. A task counts for each of its assignees.
	</p>
	{#if !rows.length}
		<div class="py-6 text-center text-sm text-gray-400">No open tasks assigned yet.</div>
	{:else}
		<div class="grid items-center gap-x-3 gap-y-1 mt-3 text-[10.5px] text-gray-400" style={GRID}>
			<span>Member</span><span class="text-right">Open</span><span class="text-right">In progress</span>
			<span class="text-right">In review</span><span class="text-right">Overdue</span>
			<span title="Relative to the busiest member">Load</span>
			<span title={HEALTH_RULE}>Health</span>
		</div>
		{#each rows as r (r.userId ?? '∅')}
			<div class="grid items-center gap-x-3 py-2 border-t border-gray-100 dark:border-gray-800 text-[12px]" style={GRID}>
				{#if r.userId}
					<span class="flex items-center gap-2 min-w-0">
						<span class="w-6 h-6 rounded-full text-white text-[10px] inline-flex items-center justify-center flex-none"
							style="background:{avatarColor(r.userId)}">{initials(r.userId)}</span>
						<span class="truncate">{displayName(r.userId)}</span>
					</span>
				{:else}
					<span class="flex items-center gap-2 text-gray-400">
						<span class="w-6 h-6 rounded-full bg-gray-100 dark:bg-gray-800 text-[10px] inline-flex items-center justify-center flex-none">—</span>
						Unassigned
					</span>
				{/if}
				<span class="text-right tabular-nums">{r.open}</span>
				<span class="text-right tabular-nums {r.userId ? '' : 'text-gray-300 dark:text-gray-600'}">{r.userId ? r.inProgress : '–'}</span>
				<span class="text-right tabular-nums {r.userId ? '' : 'text-gray-300 dark:text-gray-600'}">{r.userId ? r.inReview : '–'}</span>
				<span class="text-right tabular-nums {r.overdue ? 'text-red-600 dark:text-red-400' : 'text-gray-400'}">{r.userId ? r.overdue : '–'}</span>
				<span class="block h-[7px] rounded-full bg-gray-100 dark:bg-gray-800">
					<span class="block h-[7px] rounded-full" style="width:{Math.round(r.load * 100)}%;background:{r.userId ? '#00a5ba' : '#c9cfd7'}"></span>
				</span>
				<span>
					{#if r.health}
						<span class="text-[11px] rounded-full px-2 py-0.5 {HEALTH_PILL[r.health].cls}" title={HEALTH_RULE}>{HEALTH_PILL[r.health].label}</span>
					{:else}
						<span class="text-[11px] rounded-full px-2 py-0.5 bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400">Backlog pool</span>
					{/if}
				</span>
			</div>
		{/each}
	{/if}
</section>
