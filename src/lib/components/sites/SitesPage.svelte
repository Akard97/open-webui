<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { user } from '$lib/stores';
	import { copyToClipboard } from '$lib/utils';
	import { getSites, deleteSite } from '$lib/apis/sites';
	import SiteEditor from './SiteEditor.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';

	const i18n = getContext('i18n');

	let sites = $state<any[]>([]);
	let loaded = $state(false);
	let showEditor = $state(false);
	let editing = $state<any>(null);
	let confirmDelete = $state<any>(null);
	let showAll = $state(false);

	const levelBadge = (s: any) => {
		if (s.public) return $i18n.t('Public');
		if ((s.access_grants ?? []).some((g: any) => g.principal_id === '*')) return $i18n.t('Everyone');
		if ((s.access_grants ?? []).length > 0) return $i18n.t('Specific');
		return $i18n.t('Private');
	};

	const load = async () => {
		try {
			sites = (await getSites(localStorage.token, showAll)) ?? [];
		} catch (err) {
			toast.error(`${err}`);
		}
		loaded = true;
	};

	const copyLink = async (s: any) => {
		await copyToClipboard(`${window.location.origin}/sites/${s.slug}`);
		toast.success($i18n.t('Link copied'));
	};

	const remove = async () => {
		try {
			await deleteSite(localStorage.token, confirmDelete.id);
			toast.success($i18n.t('Site deleted'));
			confirmDelete = null;
			await load();
		} catch (err) {
			toast.error(`${err}`);
		}
	};

	onMount(load);
</script>

<div class="mx-auto w-full max-w-3xl px-4 py-6 flex flex-col gap-4">
	<div class="flex items-center justify-between">
		<div>
			<div class="text-xl font-medium dark:text-gray-100">{$i18n.t('Sites')}</div>
			<div class="text-xs text-gray-500">
				{$i18n.t('Publish static pages and share them with a link.')}
			</div>
		</div>
		<div class="flex items-center gap-2">
			{#if $user?.role === 'admin'}
				<button
					type="button"
					class="rounded-lg px-3 py-1.5 text-xs {showAll
						? 'bg-gray-100 dark:bg-gray-850 dark:text-gray-100'
						: 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-850'}"
					onclick={async () => {
						showAll = !showAll;
						await load();
					}}>{$i18n.t('All users')}</button
				>
			{/if}
			<button
				type="button"
				class="rounded-lg bg-gray-900 px-3.5 py-1.5 text-sm text-white hover:bg-gray-800 dark:bg-gray-100 dark:text-gray-900"
				onclick={() => {
					editing = null;
					showEditor = true;
				}}>{$i18n.t('New Site')}</button
			>
		</div>
	</div>

	{#if loaded && sites.length === 0}
		<div class="rounded-xl border border-dashed border-gray-200 dark:border-gray-700 py-14 text-center text-sm text-gray-500">
			{$i18n.t('Nothing published yet. Create your first site.')}
		</div>
	{:else}
		<div class="flex flex-col divide-y divide-gray-100 dark:divide-gray-850 rounded-xl border border-gray-100 dark:border-gray-850">
			{#each sites as s (s.id)}
				<div class="flex items-center gap-3 px-4 py-3">
					<div class="min-w-0 flex-1">
						<div class="flex items-center gap-2">
							<span class="truncate text-sm font-medium dark:text-gray-100">{s.name}</span>
							<span class="shrink-0 rounded bg-gray-100 dark:bg-gray-850 px-1.5 py-0.5 text-[10px] text-gray-500">
								{levelBadge(s)}
							</span>
						</div>
						<a
							class="text-xs text-gray-500 hover:underline truncate block"
							href={`/sites/${s.slug}`}
							target="_blank"
							rel="noopener">/sites/{s.slug}</a
						>
						{#if s.user_name && showAll}
							<div class="text-[10px] text-gray-400">{s.user_name}</div>
						{/if}
					</div>
					<div class="flex shrink-0 items-center gap-1 text-xs">
						<button
							type="button"
							class="rounded px-2 py-1 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-850"
							onclick={() => copyLink(s)}>{$i18n.t('Copy link')}</button
						>
						<button
							type="button"
							class="rounded px-2 py-1 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-850"
							onclick={() => {
								editing = s;
								showEditor = true;
							}}>{$i18n.t('Edit')}</button
						>
						<button
							type="button"
							class="rounded px-2 py-1 text-red-500 hover:bg-red-50 dark:hover:bg-red-950"
							onclick={() => (confirmDelete = s)}>{$i18n.t('Delete')}</button
						>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>

<SiteEditor bind:show={showEditor} site={editing} onSaved={load} />

<ConfirmDialog
	show={confirmDelete !== null}
	title={$i18n.t('Delete site?')}
	message={$i18n.t('The link will stop working immediately. This cannot be undone.')}
	on:confirm={remove}
	on:cancel={() => (confirmDelete = null)}
/>
