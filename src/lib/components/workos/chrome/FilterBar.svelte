<script lang="ts">
	import type { Writable } from 'svelte/store';
	import Icon from '../ui/Icon.svelte';
	import { STATUS_ORDER, STATUS_LABEL, PRIORITY_ORDER, type TaskFilter } from '../lib/types';
	import { labels, directory } from '../lib/store';

	export let filter: Writable<TaskFilter>;
	export let showAssignee = true;

	let open: string | null = null;
	const toggle = (k: string) => (open = open === k ? null : k);

	// Dismiss the open facet menu on any click outside that facet's own
	// chip/menu — including empty space within the filter bar itself.
	function onWindowClick(e: MouseEvent) {
		if (!open) return;
		const facet = (e.target as HTMLElement).closest?.('[data-facet]')?.getAttribute('data-facet');
		if (facet !== open) open = null;
	}

	function flip(key: 'statuses' | 'priorities' | 'labelIds' | 'assigneeIds', val: string) {
		filter.update((f) => {
			const set = new Set(f[key] as string[]);
			set.has(val) ? set.delete(val) : set.add(val);
			return { ...f, [key]: [...set] };
		});
	}
	const count = (n: number) => (n ? ` · ${n}` : '');
	$: dirEntries = Object.entries($directory);
</script>

<svelte:window onclick={onWindowClick} />

<div class="flex-none flex flex-col md:flex-row md:items-center gap-2 px-4 py-3 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
	<!-- Search: full-width row on mobile, right-aligned on desktop -->
	<div class="relative md:order-2">
		<input
			class="text-sm pl-8 pr-2 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-transparent w-full md:w-56"
			placeholder="Search title or key…"
			value={$filter.text}
			oninput={(e) => filter.update((f) => ({ ...f, text: (e.target as HTMLInputElement).value }))}
		/>
		<span class="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400"><Icon name="search" size={14} /></span>
	</div>

	<!-- Facet chips: wrap on mobile, single row + spacer role on desktop -->
	<div class="flex flex-wrap items-center gap-2 md:order-1 md:flex-1 md:flex-nowrap">
		<!-- Status -->
		<div class="relative" data-facet="status">
			<button class="filter-chip" onclick={() => toggle('status')}>
				<span class="text-gray-400">Status</span><span class="font-medium">{count($filter.statuses.length) || ' All'}</span>
				<Icon name="chevron-down" size={13} />
			</button>
			{#if open === 'status'}
				<div class="filter-menu">
					{#each STATUS_ORDER as s (s)}
						<label class="filter-item"><input type="checkbox" checked={$filter.statuses.includes(s)} onchange={() => flip('statuses', s)} /> {STATUS_LABEL[s]}</label>
					{/each}
				</div>
			{/if}
		</div>
		<!-- Priority -->
		<div class="relative" data-facet="priority">
			<button class="filter-chip" onclick={() => toggle('priority')}>
				<span class="text-gray-400">Priority</span><span class="font-medium">{count($filter.priorities.length) || ' All'}</span>
				<Icon name="chevron-down" size={13} />
			</button>
			{#if open === 'priority'}
				<div class="filter-menu">
					{#each PRIORITY_ORDER as p (p)}
						<label class="filter-item"><input type="checkbox" checked={$filter.priorities.includes(p)} onchange={() => flip('priorities', p)} /> {p}</label>
					{/each}
				</div>
			{/if}
		</div>
		<!-- Label -->
		<div class="relative" data-facet="label">
			<button class="filter-chip" onclick={() => toggle('label')}>
				<span class="text-gray-400">Label</span><span class="font-medium">{count($filter.labelIds.length) || ' All'}</span>
				<Icon name="chevron-down" size={13} />
			</button>
			{#if open === 'label'}
				<div class="filter-menu">
					{#each $labels as l (l.id)}
						<label class="filter-item"><input type="checkbox" checked={$filter.labelIds.includes(l.id)} onchange={() => flip('labelIds', l.id)} /> {l.name}</label>
					{/each}
				</div>
			{/if}
		</div>
		<!-- Assignee (hidden on My Work) -->
		{#if showAssignee}
			<div class="relative" data-facet="assignee">
				<button class="filter-chip" onclick={() => toggle('assignee')}>
					<span class="text-gray-400">Assignee</span><span class="font-medium">{count($filter.assigneeIds.length) || ' All'}</span>
					<Icon name="chevron-down" size={13} />
				</button>
				{#if open === 'assignee'}
					<div class="filter-menu">
						{#each dirEntries as [id, u] (id)}
							<label class="filter-item"><input type="checkbox" checked={$filter.assigneeIds.includes(id)} onchange={() => flip('assigneeIds', id)} /> {u.name}</label>
						{/each}
					</div>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Optional trailing controls (e.g. List view's Columns picker + Add new), placed after the search. -->
	<div class="flex items-center gap-2 md:order-3">
		<slot />
	</div>
</div>

<style>
	.filter-chip { display: inline-flex; align-items: center; gap: 0.375rem; padding: 0.375rem 0.75rem; border-radius: 0.5rem; border: 1px solid rgb(229 231 235); font-size: 0.75rem; }
	:global(.dark) .filter-chip { border-color: rgb(31 41 55); }
	.filter-menu { position: absolute; z-index: 30; margin-top: 0.25rem; min-width: 11rem; border-radius: 0.5rem; border: 1px solid rgb(229 231 235); background: white; box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1); padding: 0.25rem; }
	:global(.dark) .filter-menu { background: rgb(17 24 39); border-color: rgb(31 41 55); }
	.filter-item { display: flex; align-items: center; gap: 0.5rem; padding: 0.25rem 0.5rem; font-size: 0.8125rem; border-radius: 0.25rem; cursor: pointer; }
	.filter-item:hover { background: rgb(243 244 246); }
	:global(.dark) .filter-item:hover { background: rgb(31 41 55); }
</style>
