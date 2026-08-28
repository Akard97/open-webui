<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { user } from '$lib/stores';
	import { getSites, deleteSite } from '$lib/apis/sites';
	import { nextSelection } from './lib/selection';
	import SiteRail from './SiteRail.svelte';
	import SiteDetail from './SiteDetail.svelte';
	import CreatePanel from './CreatePanel.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import './sites.css';

	const i18n = getContext('i18n');

	let sites = $state<any[]>([]);
	let loaded = $state(false);
	let selectedId = $state<string | null>(null);
	let tab = $state('overview');
	let creating = $state(false);
	let showAll = $state(false);
	let showDeleteConfirm = $state(false);

	const selected = $derived(sites.find((s) => s.id === selectedId) ?? null);

	const load = async () => {
		try {
			sites = (await getSites(localStorage.token, showAll)) ?? [];
		} catch (err) {
			toast.error(`${err}`);
		}
		if (selectedId === null || !sites.some((s) => s.id === selectedId)) {
			selectedId = sites[0]?.id ?? null;
			tab = 'overview';
		}
		loaded = true;
	};

	const select = (id: string) => {
		creating = false;
		if (id !== selectedId) {
			selectedId = id;
			tab = 'overview';
		}
	};

	const remove = async () => {
		if (!selected) return;
		try {
			const next = nextSelection(sites, selected.id);
			await deleteSite(localStorage.token, selected.id);
			toast.success($i18n.t('Site deleted'));
			selectedId = next;
			tab = 'overview';
			await load();
		} catch (err) {
			toast.error(`${err}`);
		}
	};

	onMount(load);
</script>

<div class="sites-root h-full w-full overflow-y-auto text-gray-800 dark:text-gray-100">
	<div class="mx-auto w-full max-w-6xl px-4 py-6 md:px-8 md:py-8">
		<div class="mb-6">
			<h1 class="text-2xl font-semibold tracking-tight">{$i18n.t('Sites')}</h1>
			<div class="mt-1 text-sm text-gray-500 dark:text-gray-400">
				{$i18n.t('Publish static pages and share them with a link.')}
			</div>
		</div>

		<div class="flex flex-col gap-6 md:flex-row md:gap-8">
		<SiteRail
			{sites}
			{selectedId}
			{creating}
			{showAll}
			isAdmin={$user?.role === 'admin'}
			onSelect={select}
			onCreate={() => (creating = true)}
			onToggleAll={async (v) => {
				showAll = v;
				await load();
			}}
		/>

		{#if creating}
			<CreatePanel
				onCancel={() => (creating = false)}
				onCreated={async (site) => {
					creating = false;
					selectedId = site?.id ?? null;
					tab = 'overview';
					await load();
				}}
			/>
		{:else if selected}
			<SiteDetail site={selected} bind:tab onSaved={load} onDelete={() => (showDeleteConfirm = true)} />
			{:else if loaded}
				<div
					class="flex flex-1 flex-col items-center justify-center gap-2.5 rounded-xl border border-gray-100 px-10 py-16 text-center text-gray-500 dark:border-gray-850 dark:text-gray-400"
				>
					<div class="text-[34px]">🌐</div>
					<div class="text-[15px] font-semibold text-gray-800 dark:text-gray-100">
						{$i18n.t('Nothing published yet')}
					</div>
					<div class="max-w-xs text-[13px]">
						{$i18n.t('Upload HTML and assets — get a shareable link in seconds.')}
					</div>
					<button
						type="button"
						class="st-btn st-btn-primary st-press mt-2"
						onclick={() => (creating = true)}>{$i18n.t('Publish a Site')}</button
					>
				</div>
			{/if}
		</div>
	</div>
</div>

<ConfirmDialog
	bind:show={showDeleteConfirm}
	title={$i18n.t('Delete site?')}
	message={$i18n.t('The link will stop working immediately. This cannot be undone.')}
	on:confirm={remove}
/>
