<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import dayjs from 'dayjs';
	import relativeTime from 'dayjs/plugin/relativeTime';
	import { updateSite } from '$lib/apis/sites';
	import { siteAccessLevel } from '../lib/access';
	import FileDrop from '../FileDrop.svelte';
	import PublishConfirmDialog from '../PublishConfirmDialog.svelte';
	import ExclamationTriangle from '$lib/components/icons/ExclamationTriangle.svelte';
	import {
		htmlFileNames,
		pickEntryFile,
		mergeFiles,
		diffFiles,
		fileTile,
		totalSize,
		formatSize
	} from '../lib/form';

	dayjs.extend(relativeTime);

	const i18n = getContext('i18n');

	let { site, onSaved = () => {} }: { site: any; onSaved?: () => void } = $props();

	let staged = $state<File[]>([]);
	let entryFile = $state('');
	let saving = $state(false);
	let confirming = $state(false);

	$effect(() => {
		// reset staged state whenever the selected site changes
		site.id;
		staged = [];
		entryFile = site.entry_file ?? '';
		confirming = false;
	});

	const htmlNames = $derived(
		staged.length > 0
			? htmlFileNames(staged.map((f) => f.name))
			: htmlFileNames((site.files ?? []).map((f: any) => f.name))
	);

	$effect(() => {
		entryFile = pickEntryFile(htmlNames, entryFile);
	});

	const diff = $derived(diffFiles<{ name: string; size?: number }, File>(site.files ?? [], staged));
	const counts = $derived({
		added: diff.published.filter((p) => p.status === 'new').length,
		replaced: diff.published.filter((p) => p.status === 'replace').length,
		removed: diff.removed.length
	});

	const dirty = $derived(staged.length > 0 || entryFile !== site.entry_file);
	const isPrivate = $derived(siteAccessLevel(site) === 'private');

	const filesLabel = (n: number) =>
		n === 1 ? $i18n.t('1 file') : $i18n.t('{{count}} files', { count: n });

	const summaryStat = $derived(
		staged.length > 0
			? `${$i18n.t('Staged set')} · ${filesLabel(staged.length)} · ${formatSize(totalSize(staged))}`
			: `${filesLabel((site.files ?? []).length)} · ${formatSize(totalSize(site.files ?? []))}`
	);

	const warnText = $derived.by(() => {
		const base = $i18n.t("Publishing replaces the site's current files.");
		if (counts.removed === 0) return base;
		const removed =
			counts.removed === 1
				? $i18n.t('1 file will be removed.')
				: $i18n.t('{{count}} files will be removed.', { count: counts.removed });
		return `${base} ${removed}`;
	});

	const discard = () => {
		staged = [];
		entryFile = site.entry_file ?? '';
	};

	const requestPublish = () => {
		// Only a staged upload replaces files; an entry-file-only change is
		// non-destructive and publishes without the confirmation step.
		if (staged.length > 0) confirming = true;
		else publish();
	};

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
			confirming = false;
			onSaved();
		} catch (err) {
			toast.error(`${err}`);
		} finally {
			saving = false;
		}
	};
</script>

{#snippet tile(name: string, dimmed: boolean = false)}
	{@const t = fileTile(name)}
	<span
		class="flex h-[30px] w-[30px] flex-none items-center justify-center rounded-lg font-mono text-[8.5px] font-semibold tracking-[0.02em]
			{t.kind === 'html'
			? 'bg-[var(--st-accent-soft)] text-[var(--st-accent-soft-ink)]'
			: t.kind === 'image'
				? 'bg-[var(--st-live-soft)] text-[var(--st-live)]'
				: 'bg-[var(--st-hairline)] text-[var(--st-muted)]'} {dimmed ? 'opacity-45' : ''}"
	>
		{t.label}
	</span>
{/snippet}

<div class="st-pane flex flex-col gap-3.5">
	<div class="flex flex-wrap items-center gap-2.5">
		<span class="text-[13px] font-semibold text-[var(--st-deep)]">{summaryStat}</span>
		<span class="text-xs text-[var(--st-faint)]">·</span>
		<span class="inline-flex items-center gap-1.5 text-xs text-[var(--st-muted)]">
			<span class="st-dot {isPrivate ? 'st-dot-off' : ''}"></span>
			{$i18n.t('Published')}
			{dayjs(site.updated_at).fromNow()}
		</span>
		<span class="flex-1"></span>
		{#if staged.length > 0}
			<button type="button" class="st-btn st-btn-ghost st-press text-xs" onclick={discard}
				>{$i18n.t('Discard staged files')}</button
			>
		{/if}
	</div>

	<FileDrop
		label={staged.length === 0
			? $i18n.t('Drop a new set of files, or click to browse')
			: $i18n.t('Add more files to the staged set')}
		sublabel={staged.length === 0
			? $i18n.t(
					"Publishing a new upload replaces all current files — you'll confirm before anything goes live."
				)
			: $i18n.t('Files with the same name replace the staged copy.')}
		onFiles={(files) => (staged = mergeFiles(staged, files))}
	/>

	{#if staged.length > 0}
		<div
			class="flex items-center gap-2.5 rounded-[10px] bg-[var(--st-warn-soft)] px-3.5 py-2.5 text-[12.5px] font-medium text-[var(--st-warn)]"
		>
			<ExclamationTriangle className="w-4 h-4 flex-none" strokeWidth="1.8" />
			{warnText}
		</div>
	{/if}

	<div class="overflow-hidden rounded-xl border border-[var(--st-hairline)]">
		{#if staged.length > 0}
			<div
				class="border-b border-[var(--st-hairline)] bg-[var(--st-hover)] px-3.5 py-[7px] text-[11px] font-semibold text-[var(--st-accent-soft-ink)]"
			>
				{$i18n.t('Will be published')} · {diff.published.length}
			</div>
			{#each diff.published as p (p.file.name)}
				<div
					class="flex items-center gap-2.5 border-b border-[var(--st-hairline)] px-3.5 py-2 text-[13px] last:border-b-0"
				>
					{@render tile(p.file.name)}
					<span class="min-w-0 flex-1 truncate font-medium">{p.file.name}</span>
					{#if p.file.name === entryFile}<span class="st-pv">{$i18n.t('Entry')}</span>{/if}
					<span
						class="rounded-full px-2 py-0.5 text-[10px] font-semibold {p.status === 'new'
							? 'bg-[var(--st-live-soft)] text-[var(--st-live)]'
							: 'bg-[var(--st-accent-soft)] text-[var(--st-accent-soft-ink)]'}"
						>{p.status === 'new' ? $i18n.t('New') : $i18n.t('Replaces current')}</span
					>
					<span class="text-xs tabular-nums text-[var(--st-faint)]">{formatSize(p.file.size)}</span>
					<button
						type="button"
						class="st-press rounded px-1.5 text-[var(--st-faint)] hover:text-[var(--st-danger)]"
						aria-label={$i18n.t('Remove file')}
						onclick={() => (staged = staged.filter((x) => x.name !== p.file.name))}>✕</button
					>
				</div>
			{/each}
			{#if diff.removed.length > 0}
				<div
					class="border-b border-t border-[var(--st-hairline)] bg-[var(--st-hover)] px-3.5 py-[7px] text-[11px] font-semibold text-[var(--st-danger)]"
				>
					{$i18n.t('Will be removed')} · {diff.removed.length}
				</div>
				{#each diff.removed as f (f.name)}
					<div
						class="flex items-center gap-2.5 border-b border-[var(--st-hairline)] px-3.5 py-2 text-[13px] last:border-b-0"
					>
						{@render tile(f.name, true)}
						<span class="min-w-0 flex-1 truncate text-[var(--st-faint)] line-through">{f.name}</span
						>
						<span
							class="rounded-full bg-[var(--st-danger-soft)] px-2 py-0.5 text-[10px] font-semibold text-[var(--st-danger)]"
							>{$i18n.t('Removed')}</span
						>
						<span class="text-xs tabular-nums text-[var(--st-faint)] opacity-60"
							>{f.size != null ? formatSize(f.size) : ''}</span
						>
					</div>
				{/each}
			{/if}
		{:else}
			{#each site.files ?? [] as f (f.name)}
				<div
					class="flex items-center gap-2.5 border-b border-[var(--st-hairline)] px-3.5 py-2 text-[13px] last:border-b-0"
				>
					{@render tile(f.name)}
					<span class="min-w-0 flex-1 truncate font-medium">{f.name}</span>
					{#if f.name === entryFile}<span class="st-pv">{$i18n.t('Entry')}</span>{/if}
					<span class="text-xs tabular-nums text-[var(--st-faint)]"
						>{f.size != null ? formatSize(f.size) : ''}</span
					>
				</div>
			{/each}
		{/if}
	</div>

	<div class="flex items-center gap-2.5">
		{#if htmlNames.length > 1}
			<span class="text-[12.5px] text-[var(--st-muted)]">{$i18n.t('Opens with')}</span>
			<select
				class="rounded-[7px] border border-[var(--st-border)] bg-transparent px-2.5 py-1 text-[12.5px]"
				aria-label={$i18n.t('Opens with')}
				bind:value={entryFile}
			>
				{#each htmlNames as n (n)}
					<option value={n}>{n}</option>
				{/each}
			</select>
		{/if}
		<span class="flex-1"></span>
		{#if staged.length > 0}
			<button type="button" class="st-btn st-press" onclick={discard}>{$i18n.t('Discard')}</button>
		{/if}
		<button
			type="button"
			class="st-btn st-btn-primary st-press disabled:opacity-50"
			disabled={saving || !dirty}
			onclick={requestPublish}
			>{saving && !confirming
				? $i18n.t('Saving...')
				: staged.length > 0
					? `${$i18n.t('Publish changes')}…`
					: $i18n.t('Publish changes')}</button
		>
	</div>
</div>

<PublishConfirmDialog bind:show={confirming} {site} {counts} {saving} onConfirm={publish} />
