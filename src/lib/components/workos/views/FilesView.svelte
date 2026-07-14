<script lang="ts">
	// Files tab — every attachment across the workstream (task + comment uploads),
	// read-only: download + open-task. Upload lives on the task drawer.
	// Anatomy per docs/mockups/workos-files-v1.html (approved v1).
	import Icon from '../ui/Icon.svelte';
	import EmptyState from '../ui/EmptyState.svelte';
	import FileRow from './files/FileRow.svelte';
	import FileCard from './files/FileCard.svelte';
	import { Input } from '$lib/components/ui/input';
	import { Button } from '$lib/components/ui/button';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { wsFiles, loadWorkstreamFiles, currentWorkstreamId } from '../lib/store';
	import {
		FILE_GROUPS, FILE_SORT_LABEL, bucketFiles, filterFiles, formatBytes, groupCounts, sortFiles,
		type FileGroup, type FileSort
	} from '../lib/files';

	let ftype: FileGroup | 'all' = 'all';
	let query = '';
	let sort: FileSort = 'newest';
	let mode: 'list' | 'grid' = 'list';

	// Fetch on mount + on workstream switch (view is only mounted while active).
	$: if ($currentWorkstreamId) void loadWorkstreamFiles($currentWorkstreamId);

	const now = Date.now();

	$: counts = groupCounts($wsFiles.items);
	$: visible = sortFiles(filterFiles($wsFiles.items, ftype, query), sort);
	// Recency sections only make sense in recency order; Name/Size sorts render flat.
	$: buckets = sort === 'newest'
		? bucketFiles(visible, now)
		: visible.length ? [{ id: 'earlier' as const, label: 'All files', rows: visible }] : [];
	$: totalSize = $wsFiles.items.reduce((n, f) => n + f.size, 0);
	$: filtered = visible.length !== $wsFiles.items.length;

	const chipBase =
		'inline-flex items-center gap-1.5 h-8 px-3 rounded-full border text-xs font-medium transition-colors';
	const chipOff =
		'border-gray-200 dark:border-gray-800 text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-900';
	const chipOn = 'border-primary/45 bg-primary/10 text-primary font-semibold';

	// Header must match FileRow's grid template exactly.
	const cols =
		'grid-cols-[minmax(0,1fr)_auto_auto] md:grid-cols-[minmax(0,1fr)_180px_90px_72px_84px] xl:grid-cols-[minmax(0,1fr)_220px_150px_90px_72px_84px]';
</script>

<div class="h-full flex flex-col min-h-0">
	<!-- Toolbar: type chips · meta · sort · search · list/grid toggle -->
	<div class="flex-none flex flex-wrap items-center gap-2 px-4 py-3 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
		<button class="{chipBase} {ftype === 'all' ? chipOn : chipOff}" onclick={() => (ftype = 'all')}>
			All <span class="tabular-nums opacity-60">{counts.all}</span>
		</button>
		{#each FILE_GROUPS as g (g.id)}
			<button class="{chipBase} {ftype === g.id ? chipOn : chipOff}" onclick={() => (ftype = g.id)}>
				<span class="size-[7px] rounded-full" style="background:{g.dot}"></span>
				{g.label} <span class="tabular-nums opacity-60">{counts[g.id]}</span>
			</button>
		{/each}

		<span class="text-xs text-gray-400 px-1 whitespace-nowrap">
			{#if $wsFiles.loaded && !$wsFiles.error}
				{filtered ? `${visible.length} of ${counts.all} files` : `${counts.all} files · ${formatBytes(totalSize)}`}
			{/if}
		</span>

		<span class="flex-1"></span>

		<DropdownMenu.Root>
			<DropdownMenu.Trigger>
				{#snippet child({ props }: { props: Record<string, any> })}
					<Button {...props} variant="outline" size="sm">
						<span class="text-gray-400">Sort</span><span class="font-medium">{FILE_SORT_LABEL[sort]}</span>
						<Icon name="chevron-down" size={13} />
					</Button>
				{/snippet}
			</DropdownMenu.Trigger>
			<DropdownMenu.Content align="end" class="min-w-[9rem]">
				{#each Object.entries(FILE_SORT_LABEL) as [key, label] (key)}
					<DropdownMenu.CheckboxItem checked={sort === key} onCheckedChange={() => (sort = key as FileSort)}>
						{label}
					</DropdownMenu.CheckboxItem>
				{/each}
			</DropdownMenu.Content>
		</DropdownMenu.Root>

		<div class="relative">
			<Input class="h-8 pl-8 w-40 md:w-52" placeholder="Search files…" bind:value={query} />
			<span class="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400"><Icon name="search" size={14} /></span>
		</div>

		<span class="inline-flex rounded-lg border border-gray-200 dark:border-gray-800 overflow-hidden">
			<button
				class="grid place-items-center w-9 h-8 {mode === 'list' ? 'bg-primary/10 text-primary' : 'text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-900'}"
				title="List"
				onclick={() => (mode = 'list')}
			><Icon name="list" size={15} /></button>
			<button
				class="grid place-items-center w-9 h-8 {mode === 'grid' ? 'bg-primary/10 text-primary' : 'text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-900'}"
				title="Grid"
				onclick={() => (mode = 'grid')}
			><Icon name="layout-grid" size={15} /></button>
		</span>
	</div>

	<!-- Content -->
	<div class="flex-1 overflow-auto p-4 bg-white dark:bg-gray-900">
		{#if !$wsFiles.loaded}
			<div class="h-full flex items-center justify-center text-sm text-gray-400">Loading…</div>
		{:else if $wsFiles.error}
			<EmptyState
				icon="alert-triangle"
				title="Couldn't load files"
				sub="Something went wrong fetching this workstream's files."
				ctaLabel="Retry"
				onCta={() => $currentWorkstreamId && loadWorkstreamFiles($currentWorkstreamId)}
			/>
		{:else if !$wsFiles.items.length}
			<EmptyState
				icon="paperclip"
				title="No files yet"
				sub="Files attached to tasks in this workstream will show up here."
			/>
		{:else if !visible.length}
			<EmptyState icon="search" title="No files match" sub="Try a different type or clear the search." />
		{:else if mode === 'list'}
			<div class="space-y-3">
				{#each buckets as b (b.id)}
					<section class="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 overflow-hidden">
						<div class="flex items-center gap-2 px-3 py-2.5">
							<span class="text-sm font-semibold">{b.label}</span>
							<span class="text-xs text-gray-400 tabular-nums">{b.rows.length}</span>
						</div>
						<!-- Column header (desktop) — template mirrors FileRow -->
						<div class="hidden md:grid items-center gap-3 px-3 py-1.5 border-t border-gray-100 dark:border-gray-900 text-xs text-gray-400 {cols}">
							<span style="padding-left: 48px;">Name</span>
							<span>Task</span>
							<span class="hidden xl:block">Uploaded by</span>
							<span>Added</span>
							<span>Size</span>
							<span></span>
						</div>
						{#each b.rows as f (f.id)}
							<FileRow file={f} {now} />
						{/each}
					</section>
				{/each}
			</div>
		{:else}
			{#each buckets as b (b.id)}
				<div class="flex items-baseline gap-2 mb-2.5 mt-1 first:mt-0">
					<span class="text-sm font-semibold">{b.label}</span>
					<span class="text-xs text-gray-400 tabular-nums">{b.rows.length}</span>
				</div>
				<div class="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-3 mb-5">
					{#each b.rows as f (f.id)}
						<FileCard file={f} />
					{/each}
				</div>
			{/each}
		{/if}
	</div>
</div>
