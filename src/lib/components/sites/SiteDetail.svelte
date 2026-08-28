<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { copyToClipboard } from '$lib/utils';
	import { siteAccessLevel } from './lib/access';
	import OverviewTab from './tabs/OverviewTab.svelte';
	import FilesTab from './tabs/FilesTab.svelte';
	import SettingsTab from './tabs/SettingsTab.svelte';
	import AnalyticsTab from './tabs/AnalyticsTab.svelte';
	import VersionsTab from './tabs/VersionsTab.svelte';

	const i18n = getContext('i18n');

	let {
		site,
		tab = $bindable('overview'),
		onSaved = () => {},
		onDelete = () => {}
	}: { site: any; tab?: string; onSaved?: () => void; onDelete?: () => void } = $props();

	const url = $derived(`${window.location.origin}/sites/${site.slug}/`);
	const isPrivate = $derived(siteAccessLevel(site) === 'private');

	const tabs = $derived([
		{ id: 'overview', label: $i18n.t('Overview'), preview: false },
		{ id: 'files', label: $i18n.t('Files'), preview: false },
		{ id: 'settings', label: $i18n.t('Settings'), preview: false },
		{ id: 'analytics', label: $i18n.t('Analytics'), preview: true },
		{ id: 'versions', label: $i18n.t('Versions'), preview: true }
	]);

	let copied = $state(false);
	const copy = async () => {
		await copyToClipboard(url);
		copied = true;
		setTimeout(() => (copied = false), 1200);
		toast.success($i18n.t('Link copied'));
	};
</script>

<section class="flex min-h-0 min-w-0 flex-1 flex-col">
	<div class="flex flex-col gap-2.5 px-4 pt-4 md:px-6">
		<div class="flex flex-wrap items-start gap-3.5">
			<div class="min-w-0 flex-1">
				<h2 class="text-lg font-semibold">{site.name}</h2>
				<div class="flex items-center gap-2 text-xs">
					<a
						class="truncate text-gray-500 hover:underline dark:text-gray-400"
						href={url}
						target="_blank"
						rel="noopener">{url}</a
					>
					<button
						type="button"
						class="st-press shrink-0 rounded-md px-2 py-0.5 text-xs text-gray-500 hover:bg-gray-100 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-gray-850 dark:hover:text-gray-100"
						onclick={copy}>{copied ? $i18n.t('Copied ✓') : $i18n.t('Copy')}</button
					>
				</div>
			</div>
			<div class="flex items-center gap-2">
				<span class="st-status">
					<span class="st-dot {isPrivate ? 'st-dot-off' : ''}"></span>
					{isPrivate ? $i18n.t('Private') : $i18n.t('Live')}
				</span>
				<a class="st-btn st-press inline-flex items-center" href={url} target="_blank" rel="noopener"
					>{$i18n.t('Open')} ↗</a
				>
			</div>
		</div>
	</div>

	<div
		class="flex flex-none gap-0.5 overflow-x-auto border-b border-gray-100 px-4 pt-3 dark:border-gray-850 md:px-6"
		role="tablist"
	>
		{#each tabs as t (t.id)}
			<button
				type="button"
				role="tab"
				aria-selected={tab === t.id}
				class="relative flex items-center gap-1.5 whitespace-nowrap rounded-t-lg px-3 pb-2.5 pt-2 text-[13px] transition-colors duration-150
					{tab === t.id
					? 'font-semibold text-gray-800 after:absolute after:inset-x-2.5 after:-bottom-px after:h-0.5 after:rounded after:bg-primary after:content-[\'\'] dark:text-gray-100'
					: 'font-medium text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-100'}"
				onclick={() => (tab = t.id)}
			>
				{t.label}
				{#if t.preview}<span class="st-pv">{$i18n.t('PREVIEW')}</span>{/if}
			</button>
		{/each}
	</div>

	<div class="flex-1 overflow-y-auto px-4 pb-7 pt-5 md:px-6">
		{#if tab === 'overview'}
			<OverviewTab {site} onGoTab={(t) => (tab = t)} />
		{:else if tab === 'files'}
			<FilesTab {site} {onSaved} />
		{:else if tab === 'settings'}
			<SettingsTab {site} {onSaved} {onDelete} />
		{:else if tab === 'analytics'}
			<AnalyticsTab />
		{:else if tab === 'versions'}
			<VersionsTab />
		{/if}
	</div>
</section>
