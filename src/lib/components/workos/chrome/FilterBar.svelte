<script lang="ts">
	import type { Writable } from 'svelte/store';
	import { onDestroy } from 'svelte';
	import Icon from '../ui/Icon.svelte';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { STATUS_ORDER, STATUS_LABEL, PRIORITY_ORDER, type TaskFilter } from '../lib/types';
	import { labels, directory } from '../lib/store';
	import { track } from '$lib/utils/usage';

	export let filter: Writable<TaskFilter>;
	export let showAssignee = true;

	function flip(key: 'statuses' | 'priorities' | 'labelIds' | 'assigneeIds', val: string) {
		filter.update((f) => {
			const set = new Set(f[key] as string[]);
			set.has(val) ? set.delete(val) : set.add(val);
			return { ...f, [key]: [...set] };
		});
	}
	const count = (n: number) => (n ? ` · ${n}` : '');
	$: dirEntries = Object.entries($directory);

	// Debounced usage event: only fires 2s after the search text last changed,
	// and only while there's text to search on (clearing the box tracks nothing).
	let searchTimer: ReturnType<typeof setTimeout> | null = null;
	let lastTrackedText = '';
	$: if ($filter.text !== lastTrackedText) {
		lastTrackedText = $filter.text;
		if ($filter.text) {
			if (searchTimer) clearTimeout(searchTimer);
			searchTimer = setTimeout(() => track('workos.search.used', {}), 2000);
		} else if (searchTimer) {
			clearTimeout(searchTimer);
			searchTimer = null;
		}
	}
	onDestroy(() => {
		if (searchTimer) clearTimeout(searchTimer);
	});
</script>

<div class="flex-none flex flex-col md:flex-row md:items-center gap-2 px-4 py-3 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
	<!-- Search: full-width row on mobile, right-aligned on desktop -->
	<div class="relative md:order-2">
		<Input
			class="h-8 pl-8 w-full md:w-56"
			placeholder="Search title or key…"
			bind:value={$filter.text}
		/>
		<span class="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400"><Icon name="search" size={14} /></span>
	</div>

	<!-- Facet chips: wrap on mobile, single row + spacer role on desktop -->
	<div class="flex flex-wrap items-center gap-2 md:order-1 md:flex-1 md:flex-nowrap">
		<!-- Status -->
		<DropdownMenu.Root>
			<DropdownMenu.Trigger>
				{#snippet child({ props }: { props: Record<string, any> })}
					<Button {...props} variant="outline" size="sm">
						<span class="text-gray-400">Status</span><span class="font-medium">{count($filter.statuses.length) || ' All'}</span>
						<Icon name="chevron-down" size={13} />
					</Button>
				{/snippet}
			</DropdownMenu.Trigger>
			<DropdownMenu.Content align="start" class="min-w-[11rem]">
				<DropdownMenu.Group>
					{#each STATUS_ORDER as s (s)}
						<DropdownMenu.CheckboxItem
							checked={$filter.statuses.includes(s)}
							closeOnSelect={false}
							onCheckedChange={() => flip('statuses', s)}
						>
							{STATUS_LABEL[s]}
						</DropdownMenu.CheckboxItem>
					{/each}
				</DropdownMenu.Group>
			</DropdownMenu.Content>
		</DropdownMenu.Root>
		<!-- Priority -->
		<DropdownMenu.Root>
			<DropdownMenu.Trigger>
				{#snippet child({ props }: { props: Record<string, any> })}
					<Button {...props} variant="outline" size="sm">
						<span class="text-gray-400">Priority</span><span class="font-medium">{count($filter.priorities.length) || ' All'}</span>
						<Icon name="chevron-down" size={13} />
					</Button>
				{/snippet}
			</DropdownMenu.Trigger>
			<DropdownMenu.Content align="start" class="min-w-[11rem]">
				<DropdownMenu.Group>
					{#each PRIORITY_ORDER as p (p)}
						<DropdownMenu.CheckboxItem
							checked={$filter.priorities.includes(p)}
							closeOnSelect={false}
							onCheckedChange={() => flip('priorities', p)}
						>
							{p}
						</DropdownMenu.CheckboxItem>
					{/each}
				</DropdownMenu.Group>
			</DropdownMenu.Content>
		</DropdownMenu.Root>
		<!-- Label -->
		<DropdownMenu.Root>
			<DropdownMenu.Trigger>
				{#snippet child({ props }: { props: Record<string, any> })}
					<Button {...props} variant="outline" size="sm">
						<span class="text-gray-400">Label</span><span class="font-medium">{count($filter.labelIds.length) || ' All'}</span>
						<Icon name="chevron-down" size={13} />
					</Button>
				{/snippet}
			</DropdownMenu.Trigger>
			<DropdownMenu.Content align="start" class="min-w-[11rem]">
				<DropdownMenu.Group>
					{#each $labels as l (l.id)}
						<DropdownMenu.CheckboxItem
							checked={$filter.labelIds.includes(l.id)}
							closeOnSelect={false}
							onCheckedChange={() => flip('labelIds', l.id)}
						>
							{l.name}
						</DropdownMenu.CheckboxItem>
					{/each}
				</DropdownMenu.Group>
			</DropdownMenu.Content>
		</DropdownMenu.Root>
		<!-- Assignee (hidden on My Work) -->
		{#if showAssignee}
			<DropdownMenu.Root>
				<DropdownMenu.Trigger>
					{#snippet child({ props }: { props: Record<string, any> })}
						<Button {...props} variant="outline" size="sm">
							<span class="text-gray-400">Assignee</span><span class="font-medium">{count($filter.assigneeIds.length) || ' All'}</span>
							<Icon name="chevron-down" size={13} />
						</Button>
					{/snippet}
				</DropdownMenu.Trigger>
				<DropdownMenu.Content align="start" class="min-w-[11rem]">
					<DropdownMenu.Group>
						{#each dirEntries as [id, u] (id)}
							<DropdownMenu.CheckboxItem
								checked={$filter.assigneeIds.includes(id)}
								closeOnSelect={false}
								onCheckedChange={() => flip('assigneeIds', id)}
							>
								{u.name}
							</DropdownMenu.CheckboxItem>
						{/each}
					</DropdownMenu.Group>
				</DropdownMenu.Content>
			</DropdownMenu.Root>
		{/if}
	</div>

	<!-- Optional trailing controls (e.g. List view's Columns picker + Add new), placed after the search. -->
	<div class="flex items-center gap-2 md:order-3">
		<slot />
	</div>
</div>
