<script lang="ts">
	import { getContext } from 'svelte';
	import Modal from '$lib/components/common/Modal.svelte';

	const i18n = getContext('i18n');

	let {
		show = $bindable(false),
		site,
		counts,
		saving = false,
		onConfirm = () => {}
	}: {
		show?: boolean;
		site: any;
		counts: { added: number; replaced: number; removed: number };
		saving?: boolean;
		onConfirm?: () => void;
	} = $props();

	const chips = $derived(
		[
			{
				id: 'new',
				n: counts.added,
				label: $i18n.t('{{count}} new', { count: counts.added }),
				cls: 'bg-[var(--st-live-soft)] text-[var(--st-live)]'
			},
			{
				id: 'replaced',
				n: counts.replaced,
				label: $i18n.t('{{count}} replaced', { count: counts.replaced }),
				cls: 'bg-[var(--st-accent-soft)] text-[var(--st-accent-soft-ink)]'
			},
			{
				id: 'removed',
				n: counts.removed,
				label: $i18n.t('{{count}} removed', { count: counts.removed }),
				cls: 'bg-[var(--st-danger-soft)] text-[var(--st-danger)]'
			}
		].filter((c) => c.n > 0)
	);
</script>

<Modal bind:show size="sm" className="bg-white dark:bg-gray-900 rounded-2xl">
	<div class="sites-root px-6 pb-5 pt-[22px]">
		<h3 class="text-[15.5px] font-bold text-[var(--st-deep)]">
			{$i18n.t('Publish these changes?')}
		</h3>
		<p class="mt-0.5 text-[12.5px] text-[var(--st-muted)]">{site.name} · /sites/{site.slug}/</p>

		{#if chips.length > 0}
			<div class="mt-3.5 flex flex-wrap gap-1.5">
				{#each chips as chip (chip.id)}
					<span class="rounded-full px-2.5 py-0.5 text-[11px] font-semibold {chip.cls}"
						>{chip.label}</span
					>
				{/each}
			</div>
		{/if}

		<p class="mt-3.5 text-[12.5px] text-[var(--st-muted)]">
			{$i18n.t('This replaces everything currently on the site.')}
		</p>

		<p class="mt-2 text-xs text-[var(--st-faint)]">
			{$i18n.t('Earlier versions will be restorable soon.')}
		</p>

		<div class="mt-[18px] flex justify-end gap-2">
			<button type="button" class="st-btn st-press" onclick={() => (show = false)}
				>{$i18n.t('Cancel')}</button
			>
			<button
				type="button"
				class="st-btn st-btn-primary st-press disabled:opacity-50"
				disabled={saving}
				onclick={onConfirm}>{saving ? $i18n.t('Publishing...') : $i18n.t('Publish')}</button
			>
		</div>
	</div>
</Modal>
