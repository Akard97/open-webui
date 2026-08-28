<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { createSite } from '$lib/apis/sites';
	import FileDrop from './FileDrop.svelte';
	import VisibilityPicker from './VisibilityPicker.svelte';
	import {
		slugify,
		htmlFileNames,
		pickEntryFile,
		mergeFiles,
		grantsForLevel,
		formatSize
	} from './lib/form';

	const i18n = getContext('i18n');

	let { onCancel = () => {}, onCreated = (_site: any) => {} }: { onCancel?: () => void; onCreated?: (site: any) => void } = $props();

	let name = $state('');
	let slug = $state('');
	let slugTouched = $state(false);
	let level = $state('private');
	let accessGrants = $state<any[]>([]);
	let files = $state<File[]>([]);
	let entryFile = $state('');
	let saving = $state(false);

	$effect(() => {
		if (!slugTouched) slug = slugify(name);
	});

	const htmlNames = $derived(htmlFileNames(files.map((f) => f.name)));

	$effect(() => {
		entryFile = pickEntryFile(htmlNames, entryFile);
	});

	const submit = async () => {
		saving = true;
		try {
			const fd = new FormData();
			fd.append('name', name);
			fd.append('slug', slug);
			fd.append('public', level === 'public' ? 'true' : 'false');
			fd.append('access_grants', JSON.stringify(grantsForLevel(level, accessGrants)));
			if (entryFile) fd.append('entry_file', entryFile);
			for (const f of files) fd.append('files', f);
			const site = await createSite(localStorage.token, fd);
			toast.success($i18n.t('Site saved'));
			onCreated(site);
		} catch (err) {
			toast.error(`${err}`);
		} finally {
			saving = false;
		}
	};
</script>

<div class="st-pane flex max-w-xl flex-col px-8 py-8 sm:px-10">
	<h3 class="text-lg font-semibold tracking-tight">{$i18n.t('Publish a Site')}</h3>
	<p class="mb-5 text-[13px] text-[var(--st-muted)]">
		{$i18n.t('Upload HTML and assets — get a shareable link in seconds.')}
	</p>

	<div class="mb-4 flex flex-col gap-1">
		<label class="text-xs font-semibold text-[var(--st-muted)]" for="st-new-name"
			>{$i18n.t('Name')}</label
		>
		<input
			id="st-new-name"
			class="rounded-[9px] border border-[var(--st-border)] bg-transparent px-2.5 py-2 text-[13.5px] outline-none focus:border-[var(--st-accent)]"
			bind:value={name}
			placeholder={$i18n.t('My page')}
		/>
	</div>
	<div class="mb-4 flex flex-col gap-1">
		<label class="text-xs font-semibold text-[var(--st-muted)]" for="st-new-slug"
			>{$i18n.t('Link')}</label
		>
		<div class="flex items-center gap-1 text-sm">
			<span class="shrink-0 font-mono text-[12.5px] text-[var(--st-faint)]"
				>{window.location.origin}/sites/</span
			>
			<input
				id="st-new-slug"
				class="min-w-0 flex-1 rounded-[9px] border border-[var(--st-border)] bg-transparent px-2.5 py-2 font-mono text-[12.5px] outline-none focus:border-[var(--st-accent)]"
				bind:value={slug}
				oninput={() => (slugTouched = true)}
			/>
		</div>
	</div>

	<div class="mb-1.5 text-xs font-semibold text-[var(--st-muted)]">{$i18n.t('Files')}</div>
	<FileDrop
		label={$i18n.t('Drop your HTML and asset files here, or click to browse')}
		onFiles={(list) => (files = mergeFiles(files, list))}
	/>
	{#if files.length > 0}
		<div class="mt-1.5 flex flex-col gap-1">
			{#each files as f (f.name)}
				<div class="flex items-center justify-between text-xs text-[var(--st-muted)]">
					<span class="truncate font-mono">{f.name}</span>
					<div class="flex shrink-0 items-center gap-2">
						{#if f.name === entryFile}<span class="st-pv">{$i18n.t('ENTRY')}</span>{/if}
						<span class="tabular-nums text-[var(--st-faint)]">{formatSize(f.size)}</span>
						<button
							type="button"
							class="text-[var(--st-faint)] hover:text-[var(--st-danger)]"
							aria-label={$i18n.t('Remove file')}
							onclick={() => (files = files.filter((x) => x.name !== f.name))}>✕</button
						>
					</div>
				</div>
			{/each}
		</div>
	{/if}
	{#if htmlNames.length > 1}
		<div class="mt-1.5 flex items-center gap-2 text-xs">
			<span class="text-[var(--st-muted)]">{$i18n.t('Opens with')}</span>
			<select
				class="rounded border border-[var(--st-border)] bg-transparent px-2 py-1 font-mono"
				aria-label={$i18n.t('Opens with')}
				bind:value={entryFile}
			>
				{#each htmlNames as n (n)}
					<option value={n}>{n}</option>
				{/each}
			</select>
		</div>
	{/if}

	<div class="mb-1.5 mt-4 text-xs font-semibold text-[var(--st-muted)]">
		{$i18n.t('Who can view')}
	</div>
	<VisibilityPicker bind:level bind:accessGrants />

	<div class="mt-5 flex gap-2">
		<button type="button" class="st-btn" disabled={saving} onclick={onCancel}
			>{$i18n.t('Cancel')}</button
		>
		<button
			type="button"
			class="st-btn st-btn-primary disabled:opacity-50"
			disabled={saving || !name.trim() || !slug || files.length === 0}
			onclick={submit}>{saving ? $i18n.t('Saving...') : $i18n.t('Publish')}</button
		>
	</div>
</div>
