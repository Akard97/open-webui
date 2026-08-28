<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import dayjs from 'dayjs';
	import relativeTime from 'dayjs/plugin/relativeTime';
	import { copyToClipboard } from '$lib/utils';
	import { siteAccessLevel } from '../lib/access';
	import { totalSize, formatSize } from '../lib/form';

	dayjs.extend(relativeTime);

	const i18n = getContext('i18n');

	let { site, onGoTab = (_t: string) => {} }: { site: any; onGoTab?: (t: string) => void } =
		$props();

	const url = $derived(`${window.location.origin}/sites/${site.slug}/`);
	const level = $derived(siteAccessLevel(site));

	const visLabel = $derived(
		{
			public: $i18n.t('Public'),
			internal: $i18n.t('Everyone'),
			specific: $i18n.t('Specific'),
			private: $i18n.t('Private')
		}[level]
	);
	const visSub = $derived(
		{
			public: $i18n.t('No login needed'),
			internal: $i18n.t('Signed-in viewers'),
			specific: $i18n.t('Signed-in viewers'),
			private: $i18n.t('Only you')
		}[level]
	);

	const copy = async () => {
		await copyToClipboard(url);
		toast.success($i18n.t('Link copied'));
	};
</script>

<div class="st-pane flex flex-col gap-4">
	<div
		class="flex flex-wrap items-center gap-3 rounded-xl bg-gray-50 px-4 py-3.5 dark:bg-gray-850"
	>
		<span class="min-w-0 flex-1 truncate text-sm text-gray-600 dark:text-gray-300">{url}</span>
		<div class="flex gap-2">
			<button type="button" class="st-btn" onclick={copy}>{$i18n.t('Copy link')}</button>
			<a class="st-btn st-btn-primary inline-flex items-center" href={url} target="_blank" rel="noopener"
				>{$i18n.t('Open site')} ↗</a
			>
		</div>
	</div>

	<div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
		<div class="rounded-xl border border-[var(--st-hairline)] px-3.5 py-3">
			<div
				class="flex items-center gap-1.5 text-xs font-medium text-gray-400 dark:text-gray-500"
			>
				{$i18n.t('Views · 7d')} <span class="st-pv">{$i18n.t('PREVIEW')}</span>
			</div>
			<div class="mt-0.5 text-[21px] font-bold tabular-nums tracking-tight">1,284</div>
			<div class="text-[11.5px] text-[var(--st-muted)]">{$i18n.t('Sample data')}</div>
		</div>
		<div class="rounded-xl border border-[var(--st-hairline)] px-3.5 py-3">
			<div class="text-xs font-medium text-gray-400 dark:text-gray-500">
				{$i18n.t('Files')}
			</div>
			<div class="mt-0.5 text-[21px] font-bold tabular-nums tracking-tight">
				{(site.files ?? []).length}
			</div>
			<div class="text-[11.5px] text-[var(--st-muted)]">
				{formatSize(totalSize(site.files ?? []))}
				{$i18n.t('total')}
			</div>
		</div>
		<div class="rounded-xl border border-[var(--st-hairline)] px-3.5 py-3">
			<div class="text-xs font-medium text-gray-400 dark:text-gray-500">
				{$i18n.t('Visibility')}
			</div>
			<div class="mt-1 text-[16px] font-bold tracking-tight">{visLabel}</div>
			<div class="text-[11.5px] text-[var(--st-muted)]">{visSub}</div>
		</div>
		<div class="rounded-xl border border-[var(--st-hairline)] px-3.5 py-3">
			<div class="text-xs font-medium text-gray-400 dark:text-gray-500">
				{$i18n.t('Updated')}
			</div>
			<div class="mt-1 text-[16px] font-bold tracking-tight">
				{dayjs(site.updated_at * 1000).fromNow()}
			</div>
			<div class="text-[11.5px] text-[var(--st-muted)]">
				{$i18n.t('Created')} {dayjs(site.created_at * 1000).format('MMM D, YYYY')}
			</div>
		</div>
	</div>

	<div class="grid grid-cols-1 gap-3 md:grid-cols-2">
		<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-3.5">
			<h4
				class="mb-2 text-xs font-medium text-gray-400 dark:text-gray-500"
			>
				{$i18n.t('Details')}
			</h4>
			<div
				class="flex justify-between border-b border-[var(--st-hairline)] py-1.5 text-[13px]"
			>
				<span class="text-[var(--st-muted)]">{$i18n.t('Entry file')}</span>
				<span>{site.entry_file}</span>
			</div>
			<div class="flex justify-between py-1.5 text-[13px]">
				<span class="text-[var(--st-muted)]">{$i18n.t('Owner')}</span>
				<span>{site.user_name ?? $i18n.t('You')}</span>
			</div>
		</div>
		<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-3.5">
			<h4
				class="mb-2 text-xs font-medium text-gray-400 dark:text-gray-500"
			>
				{$i18n.t('Quick actions')}
			</h4>
			{#each [[$i18n.t('Replace files'), $i18n.t('Go to Files'), 'files'], [$i18n.t('Change who can view'), $i18n.t('Go to Settings'), 'settings'], [$i18n.t('Restore an older version'), $i18n.t('Go to Versions'), 'versions']] as [label, cta, tab], i (tab)}
				<div
					class="flex items-center justify-between py-1.5 text-[13px] {i < 2
						? 'border-b border-[var(--st-hairline)]'
						: ''}"
				>
					<span class="text-[var(--st-muted)]">{label}</span>
					<button
						type="button"
						class="st-press rounded-[7px] px-2 py-1 text-xs text-[var(--st-muted)] hover:bg-[var(--st-hover)] hover:text-[var(--st-ink)]"
						onclick={() => onGoTab(tab as string)}>{cta} →</button
					>
				</div>
			{/each}
		</div>
	</div>
</div>
