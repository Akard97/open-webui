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

<div class="sites-root mx-auto w-full max-w-[1160px] px-4 py-7 pb-10">
	<div class="mx-1 mb-4 flex flex-wrap items-baseline gap-3">
		<h1 class="text-[22px] font-bold tracking-tight">{$i18n.t('Sites')}</h1>
		<span class="text-[13px] text-[var(--st-muted)]"
			>{$i18n.t('Publish static pages and share them with a link.')}</span
		>
	</div>

	<div
		class="grid min-h-[640px] grid-cols-1 overflow-hidden rounded-2xl border border-[var(--st-border)] bg-[var(--st-card)] shadow-[var(--st-shadow)] md:grid-cols-[280px_1fr]"
	>
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
				class="flex flex-col items-center justify-center gap-2.5 px-10 py-16 text-center text-[var(--st-muted)]"
			>
				<div class="text-[34px]">🌐</div>
				<div class="text-[15px] font-semibold text-[var(--st-ink)]">
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

<ConfirmDialog
	bind:show={showDeleteConfirm}
	title={$i18n.t('Delete site?')}
	message={$i18n.t('The link will stop working immediately. This cannot be undone.')}
	on:confirm={remove}
/>
