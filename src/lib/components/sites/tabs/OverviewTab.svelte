<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import dayjs from 'dayjs';
	import relativeTime from 'dayjs/plugin/relativeTime';
	import { copyToClipboard } from '$lib/utils';
	import { siteAccessLevel } from '../lib/access';
	import { totalSize, formatSize } from '../lib/form';
	import InsightsCard from '../InsightsCard.svelte';

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
	<div class="flex flex-wrap items-center gap-3 rounded-xl bg-gray-50 px-4 py-3.5 dark:bg-gray-850">
		<span class="min-w-0 flex-1 truncate text-sm text-gray-600 dark:text-gray-300">{url}</span>
		<div class="flex gap-2">
			<button type="button" class="st-btn" onclick={copy}>{$i18n.t('Copy link')}</button>
			<a
				class="st-btn st-btn-primary inline-flex items-center"
				href={url}
				target="_blank"
				rel="noopener">{$i18n.t('Open site')} ↗</a
			>
		</div>
	</div>

	<InsightsCard {site} />

	<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-3.5">
		<h4 class="mb-2 text-xs font-medium text-gray-400 dark:text-gray-500">
			{$i18n.t('Details')}
		</h4>
		{#each [[$i18n.t('Visibility'), `${visLabel} · ${visSub}`], [$i18n.t('Entry file'), site.entry_file], [$i18n.t('Files'), `${(site.files ?? []).length} · ${formatSize(totalSize(site.files ?? []))}`], [$i18n.t('Owner'), site.user_name ?? $i18n.t('You')], [$i18n.t('Updated'), `${dayjs(site.updated_at).fromNow()} · ${$i18n.t('created')} ${dayjs(site.created_at).format('MMM D, YYYY')}`]] as [label, value], i (label)}
			<div
				class="flex justify-between gap-3 py-1.5 text-[13px] {i < 4
					? 'border-b border-[var(--st-hairline)]'
					: ''}"
			>
				<span class="text-[var(--st-muted)]">{label}</span>
				<span class="truncate text-right">{value}</span>
			</div>
		{/each}
	</div>

	<div class="flex flex-wrap items-center gap-1.5">
		{#each [[$i18n.t('Replace files'), 'files'], [$i18n.t('Change who can view'), 'settings'], [$i18n.t('Restore an older version'), 'versions']] as [label, target] (target)}
			<button
				type="button"
				class="st-press rounded-[7px] px-2.5 py-1.5 text-xs text-[var(--st-muted)] hover:bg-[var(--st-hover)] hover:text-[var(--st-ink)]"
				onclick={() => onGoTab(target as string)}>{label} →</button
			>
		{/each}
	</div>
</div>
