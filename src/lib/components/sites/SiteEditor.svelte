<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { getContext } from 'svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import AccessControl from '$lib/components/workspace/common/AccessControl.svelte';
	import { createSite, updateSite, updateSiteAccess } from '$lib/apis/sites';

	const i18n = getContext('i18n');

	let {
		show = $bindable(false),
		site = null, // null => create mode
		onSaved = () => {}
	} = $props();

	let name = $state('');
	let slug = $state('');
	let slugTouched = $state(false);
	let level = $state('private'); // 'public' | 'internal' | 'specific' | 'private'
	let accessGrants = $state<any[]>([]);
	let files = $state<File[]>([]);
	let entryFile = $state('');
	let saving = $state(false);
	let dragging = $state(false);
	let openSeq = 0;

	const slugify = (v: string) =>
		v
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, '-')
			.replace(/^-+|-+$/g, '')
			.slice(0, 60);

	$effect(() => {
		if (show) {
			openSeq += 1;
			name = site?.name ?? '';
			slug = site?.slug ?? '';
			slugTouched = !!site;
			files = [];
			entryFile = site?.entry_file ?? '';
			if (site?.public) level = 'public';
			else if ((site?.access_grants ?? []).some((g: any) => g.principal_id === '*')) level = 'internal';
			else if ((site?.access_grants ?? []).length > 0) level = 'specific';
			else level = 'private';
			accessGrants = (site?.access_grants ?? []).filter((g: any) => g.principal_id !== '*');
		}
	});

	$effect(() => {
		if (!slugTouched) slug = slugify(name);
	});

	let htmlNames = $derived(
		files.length > 0
			? files.filter((f) => /\.html?$/i.test(f.name)).map((f) => f.name)
			: (site?.files ?? []).filter((f: any) => /\.html?$/i.test(f.name)).map((f: any) => f.name)
	);

	$effect(() => {
		if (htmlNames.length > 0 && !htmlNames.includes(entryFile)) {
			entryFile = htmlNames.includes('index.html') ? 'index.html' : htmlNames[0];
		}
	});

	const addFiles = (list: FileList | File[] | null) => {
		if (!list) return;
		const next = [...files];
		for (const f of Array.from(list)) {
			if (!next.some((x) => x.name === f.name)) next.push(f);
		}
		files = next;
	};

	const grantsForLevel = () => {
		if (level === 'internal') return [{ principal_type: 'user', principal_id: '*', permission: 'read' }];
		if (level === 'specific') return accessGrants.filter((g) => g.principal_id !== '*');
		return [];
	};

	const submit = async () => {
		const seq = openSeq;
		saving = true;
		try {
			if (!site) {
				const fd = new FormData();
				fd.append('name', name);
				fd.append('slug', slug);
				fd.append('public', level === 'public' ? 'true' : 'false');
				fd.append('access_grants', JSON.stringify(grantsForLevel()));
				if (entryFile) fd.append('entry_file', entryFile);
				for (const f of files) fd.append('files', f);
				await createSite(localStorage.token, fd);
			} else {
				const fd = new FormData();
				fd.append('name', name);
				fd.append('slug', slug);
				if (entryFile) fd.append('entry_file', entryFile);
				for (const f of files) fd.append('files', f);
				await updateSite(localStorage.token, site.id, fd);
				await updateSiteAccess(localStorage.token, site.id, {
					public: level === 'public',
					access_grants: grantsForLevel()
				});
			}
			if (seq !== openSeq || !show) {
				onSaved(); // server state did change; refresh the list, but don't touch the (re)opened dialog
				return;
			}
			toast.success($i18n.t('Site saved'));
			show = false;
			onSaved();
		} catch (err) {
			toast.error(`${err}`);
		} finally {
			saving = false;
		}
	};
</script>

<Modal size="md" bind:show>
	<div class="p-5 flex flex-col gap-4">
		<div class="text-lg font-medium dark:text-gray-100">
			{site ? $i18n.t('Edit Site') : $i18n.t('Publish a Site')}
		</div>

		<div class="flex flex-col gap-1">
			<label class="text-xs font-medium text-gray-500" for="site-name">{$i18n.t('Name')}</label>
			<input
				id="site-name"
				class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-transparent px-3 py-2 text-sm outline-none dark:text-gray-100"
				bind:value={name}
				placeholder={$i18n.t('My page')}
			/>
		</div>

		<div class="flex flex-col gap-1">
			<label class="text-xs font-medium text-gray-500" for="site-slug">{$i18n.t('Link')}</label>
			<div class="flex items-center gap-1 text-sm">
				<span class="text-gray-400 shrink-0">{window.location.origin}/sites/</span>
				<input
					id="site-slug"
					class="flex-1 min-w-0 rounded-lg border border-gray-200 dark:border-gray-700 bg-transparent px-3 py-2 text-sm outline-none dark:text-gray-100"
					bind:value={slug}
					oninput={() => (slugTouched = true)}
				/>
			</div>
		</div>

		<div class="flex flex-col gap-1">
			<div class="text-xs font-medium text-gray-500">{$i18n.t('Files')}</div>
			<button
				type="button"
				class="rounded-xl border-2 border-dashed px-4 py-6 text-sm text-gray-500 transition
					{dragging ? 'border-gray-500 bg-gray-50 dark:bg-gray-850' : 'border-gray-200 dark:border-gray-700'}"
				ondragover={(e) => {
					e.preventDefault();
					dragging = true;
				}}
				ondragleave={() => (dragging = false)}
				ondrop={(e) => {
					e.preventDefault();
					dragging = false;
					addFiles(e.dataTransfer?.files ?? null);
				}}
				onclick={() => document.getElementById('site-files-input')?.click()}
			>
				{site && files.length === 0
					? $i18n.t('Drop files to replace the current ones, or click to browse')
					: $i18n.t('Drop your HTML and asset files here, or click to browse')}
			</button>
			<input
				id="site-files-input"
				type="file"
				multiple
				hidden
				onchange={(e) => {
					addFiles((e.target as HTMLInputElement).files);
					(e.target as HTMLInputElement).value = '';
				}}
			/>
			{#if files.length > 0}
				<div class="flex flex-col gap-1 mt-1">
					{#each files as f (f.name)}
						<div class="flex items-center justify-between text-xs text-gray-600 dark:text-gray-300">
							<span class="truncate">{f.name}</span>
							<div class="flex items-center gap-2 shrink-0">
								<span class="text-gray-400">{(f.size / 1024).toFixed(1)} KB</span>
								<button
									type="button"
									class="text-gray-400 hover:text-red-500"
									aria-label={$i18n.t('Remove file')}
									onclick={() => (files = files.filter((x) => x.name !== f.name))}>&times;</button
								>
							</div>
						</div>
					{/each}
				</div>
			{:else if site}
				<div class="text-xs text-gray-400">
					{$i18n.t('{{count}} file(s) currently published', { count: (site.files ?? []).length })}
				</div>
			{/if}
			{#if htmlNames.length > 1}
				<div class="flex items-center gap-2 mt-1 text-xs">
					<span class="text-gray-500">{$i18n.t('Opens with')}</span>
					<select
						class="rounded border border-gray-200 dark:border-gray-700 bg-transparent px-2 py-1 dark:text-gray-100"
						aria-label={$i18n.t('Opens with')}
						bind:value={entryFile}
					>
						{#each htmlNames as n (n)}
							<option value={n}>{n}</option>
						{/each}
					</select>
				</div>
			{/if}
		</div>

		<div class="flex flex-col gap-2">
			<div class="text-xs font-medium text-gray-500">{$i18n.t('Who can view')}</div>
			<div class="flex flex-col gap-1.5 text-sm dark:text-gray-100">
				{#each [
					['private', $i18n.t('Only me')],
					['specific', $i18n.t('Specific people or groups')],
					['internal', $i18n.t('Everyone with an account')],
					['public', $i18n.t('Public — no login needed')]
				] as [value, label] (value)}
					<label class="flex items-center gap-2">
						<input type="radio" name="site-level" {value} bind:group={level} />
						{label}
					</label>
				{/each}
			</div>
			{#if level === 'specific'}
				<AccessControl bind:accessGrants accessRoles={['read']} sharePublic={false} />
			{/if}
		</div>

		<div class="flex justify-end gap-2 pt-1">
			<button
				type="button"
				class="rounded-lg px-3.5 py-1.5 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-850"
				disabled={saving}
				onclick={() => (show = false)}>{$i18n.t('Cancel')}</button
			>
			<button
				type="button"
				class="rounded-lg bg-gray-900 px-3.5 py-1.5 text-sm text-white hover:bg-gray-800 dark:bg-gray-100 dark:text-gray-900 disabled:opacity-50"
				disabled={saving || !name.trim() || !slug || (!site && files.length === 0)}
				onclick={submit}>{saving ? $i18n.t('Saving...') : site ? $i18n.t('Save') : $i18n.t('Publish')}</button
			>
		</div>
	</div>
</Modal>
