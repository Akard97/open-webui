<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { updateSite } from '$lib/apis/sites';
	import FileDrop from '../FileDrop.svelte';
	import { htmlFileNames, pickEntryFile, mergeFiles, formatSize } from '../lib/form';

	const i18n = getContext('i18n');

	let { site, onSaved = () => {} }: { site: any; onSaved?: () => void } = $props();

	let staged = $state<File[]>([]);
	let entryFile = $state('');
	let saving = $state(false);

	$effect(() => {
		// reset staged state whenever the selected site changes
		site.id;
		staged = [];
		entryFile = site.entry_file ?? '';
	});

	const htmlNames = $derived(
		staged.length > 0
			? htmlFileNames(staged.map((f) => f.name))
			: htmlFileNames((site.files ?? []).map((f: any) => f.name))
	);

	$effect(() => {
		entryFile = pickEntryFile(htmlNames, entryFile);
	});

	const dirty = $derived(staged.length > 0 || entryFile !== site.entry_file);

	const publish = async () => {
		saving = true;
		try {
			const fd = new FormData();
			fd.append('name', site.name);
			fd.append('slug', site.slug);
			if (entryFile) fd.append('entry_file', entryFile);
			for (const f of staged) fd.append('files', f);
			await updateSite(localStorage.token, site.id, fd);
			toast.success($i18n.t('Site saved'));
			staged = [];
			onSaved();
		} catch (err) {
			toast.error(`${err}`);
		} finally {
			saving = false;
		}
	};
</script>

<div class="st-pane flex flex-col gap-3.5">
	<FileDrop
		label={staged.length === 0
			? $i18n.t('Drop files to replace the current ones, or click to browse')
			: $i18n.t('Drop more files, or click to browse')}
		onFiles={(files) => (staged = mergeFiles(staged, files))}
	/>

	<div class="overflow-hidden rounded-xl border border-[var(--st-hairline)]">
		{#if staged.length > 0}
			{#each staged as f (f.name)}
				<div
					class="flex items-center gap-2.5 border-b border-[var(--st-hairline)] px-3 py-2 text-[13px] last:border-b-0"
				>
					<span class="min-w-0 flex-1 truncate font-mono">{f.name}</span>
					{#if f.name === entryFile}<span class="st-pv">{$i18n.t('ENTRY')}</span>{/if}
					<span class="text-xs tabular-nums text-[var(--st-faint)]">{formatSize(f.size)}</span>
					<button
						type="button"
						class="st-press rounded px-1.5 text-[var(--st-faint)] hover:text-[var(--st-danger)]"
						aria-label={$i18n.t('Remove file')}
						onclick={() => (staged = staged.filter((x) => x.name !== f.name))}>✕</button
					>
				</div>
			{/each}
		{:else}
			{#each site.files ?? [] as f (f.name)}
				<div
					class="flex items-center gap-2.5 border-b border-[var(--st-hairline)] px-3 py-2 text-[13px] last:border-b-0"
				>
					<span class="min-w-0 flex-1 truncate font-mono">{f.name}</span>
					{#if f.name === entryFile}<span class="st-pv">{$i18n.t('ENTRY')}</span>{/if}
					<span class="text-xs tabular-nums text-[var(--st-faint)]"
						>{f.size != null ? formatSize(f.size) : ''}</span
					>
				</div>
			{/each}
		{/if}
	</div>
	{#if staged.length > 0}
		<div class="text-xs text-[var(--st-faint)]">
			{$i18n.t('Publishing replaces all current files with the ones above.')}
		</div>
	{/if}

	<div class="flex items-center gap-2.5">
		{#if htmlNames.length > 1}
			<span class="text-[12.5px] text-[var(--st-muted)]">{$i18n.t('Opens with')}</span>
			<select
				class="rounded-[7px] border border-[var(--st-border)] bg-transparent px-2.5 py-1 font-mono text-[12.5px]"
				aria-label={$i18n.t('Opens with')}
				bind:value={entryFile}
			>
				{#each htmlNames as n (n)}
					<option value={n}>{n}</option>
				{/each}
			</select>
		{/if}
		<button
			type="button"
			class="st-btn st-btn-primary ml-auto disabled:opacity-50"
			disabled={saving || !dirty}
			onclick={publish}
			>{saving ? $i18n.t('Saving...') : $i18n.t('Publish changes')}</button
		>
	</div>
</div>
