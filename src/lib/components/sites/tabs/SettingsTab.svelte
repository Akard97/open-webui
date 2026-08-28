<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { updateSite, updateSiteAccess } from '$lib/apis/sites';
	import VisibilityPicker from '../VisibilityPicker.svelte';
	import { grantsForLevel } from '../lib/form';
	import { isEveryoneGrant, siteAccessLevel } from '../lib/access';

	const i18n = getContext('i18n');

	let { site, onSaved = () => {}, onDelete = () => {} }: { site: any; onSaved?: () => void; onDelete?: () => void } = $props();

	let name = $state('');
	let slug = $state('');
	let level = $state('private');
	let accessGrants = $state<any[]>([]);
	let saving = $state(false);

	$effect(() => {
		site.id;
		name = site.name ?? '';
		slug = site.slug ?? '';
		level = siteAccessLevel(site);
		accessGrants = (site.access_grants ?? []).filter((g: any) => !isEveryoneGrant(g));
	});

	const save = async () => {
		saving = true;
		try {
			const fd = new FormData();
			fd.append('name', name);
			fd.append('slug', slug);
			await updateSite(localStorage.token, site.id, fd);
			try {
				await updateSiteAccess(localStorage.token, site.id, {
					public: level === 'public',
					access_grants: grantsForLevel(level, accessGrants)
				});
			} catch (err) {
				// The name/slug call above already committed — say so, instead of a
				// generic error implying nothing was saved.
				toast.error(
					$i18n.t('Site files saved, but updating who can view failed: {{error}}', {
						error: `${err}`
					})
				);
				onSaved();
				return;
			}
			toast.success($i18n.t('Site saved'));
			onSaved();
		} catch (err) {
			toast.error(`${err}`);
		} finally {
			saving = false;
		}
	};
</script>

<div class="st-pane flex flex-col">
	<div class="mb-4 flex max-w-md flex-col gap-1">
		<label class="text-xs font-semibold text-[var(--st-muted)]" for="st-name"
			>{$i18n.t('Name')}</label
		>
		<input
			id="st-name"
			class="rounded-[9px] border border-[var(--st-border)] bg-transparent px-2.5 py-2 text-[13.5px] outline-none focus:border-[var(--st-accent)]"
			bind:value={name}
		/>
	</div>
	<div class="mb-4 flex max-w-md flex-col gap-1">
		<label class="text-xs font-semibold text-[var(--st-muted)]" for="st-slug"
			>{$i18n.t('Link')}</label
		>
		<div class="flex items-center gap-1 text-sm">
			<span class="shrink-0 font-mono text-[12.5px] text-[var(--st-faint)]"
				>{window.location.origin}/sites/</span
			>
			<input
				id="st-slug"
				class="min-w-0 flex-1 rounded-[9px] border border-[var(--st-border)] bg-transparent px-2.5 py-2 font-mono text-[12.5px] outline-none focus:border-[var(--st-accent)]"
				bind:value={slug}
			/>
		</div>
	</div>

	<div class="mb-2 text-xs font-semibold text-[var(--st-muted)]">{$i18n.t('Who can view')}</div>
	<VisibilityPicker bind:level bind:accessGrants />

	<div class="mt-4">
		<button
			type="button"
			class="st-btn st-btn-primary disabled:opacity-50"
			disabled={saving || !name.trim() || !slug}
			onclick={save}>{saving ? $i18n.t('Saving...') : $i18n.t('Save changes')}</button
		>
	</div>

	<div
		class="mt-6 max-w-md rounded-xl border border-[color-mix(in_oklab,var(--st-danger)_30%,transparent)] px-4 py-3.5"
	>
		<h4 class="mb-1 text-[13px] font-semibold text-[var(--st-danger)]">
			{$i18n.t('Delete this site')}
		</h4>
		<p class="mb-2.5 text-[12.5px] text-[var(--st-muted)]">
			{$i18n.t('The link will stop working immediately. This cannot be undone.')}
		</p>
		<button type="button" class="st-btn st-btn-danger" onclick={onDelete}
			>{$i18n.t('Delete site...')}</button
		>
	</div>
</div>
