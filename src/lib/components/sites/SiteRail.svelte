<script lang="ts">
	import { getContext } from 'svelte';
	import { siteAccessLevel } from './lib/access';

	const i18n = getContext('i18n');

	let {
		sites = [],
		selectedId = null,
		creating = false,
		showAll = false,
		isAdmin = false,
		onSelect = (_id: string) => {},
		onCreate = () => {},
		onToggleAll = (_v: boolean) => {}
	}: {
		sites?: any[];
		selectedId?: string | null;
		creating?: boolean;
		showAll?: boolean;
		isAdmin?: boolean;
		onSelect?: (id: string) => void;
		onCreate?: () => void;
		onToggleAll?: (v: boolean) => void;
	} = $props();

	const levelBadge = (s: any) => {
		const labels: Record<string, string> = {
			public: $i18n.t('Public'),
			internal: $i18n.t('Everyone'),
			specific: $i18n.t('Specific'),
			private: $i18n.t('Private')
		};
		return labels[siteAccessLevel(s)];
	};
</script>

<aside
	class="flex flex-col border-b border-[var(--st-hairline)] bg-[color-mix(in_oklab,var(--st-card)_60%,var(--st-ground))] md:border-b-0 md:border-r"
>
	<div class="flex flex-col gap-2.5 px-3.5 pb-2.5 pt-4">
		<button
			type="button"
			class="st-press flex items-center justify-center gap-1.5 rounded-[10px] bg-[var(--st-accent)] px-3 py-2 text-[13.5px] font-semibold text-[var(--st-accent-ink)]"
			onclick={onCreate}
		>
			＋ {$i18n.t('New site')}
		</button>
		{#if isAdmin}
			<div class="flex rounded-lg bg-[var(--st-hairline)] p-0.5 text-xs">
				{#each [[false, $i18n.t('My sites')], [true, $i18n.t('All users')]] as [value, label] (label)}
					<button
						type="button"
						class="flex-1 rounded-md px-2 py-1 font-medium transition-colors duration-150
							{showAll === value
							? 'bg-[var(--st-card)] text-[var(--st-ink)] shadow-sm'
							: 'text-[var(--st-muted)]'}"
						onclick={() => onToggleAll(value as boolean)}>{label}</button
					>
				{/each}
			</div>
		{/if}
	</div>
	<nav class="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 pb-3.5 pt-1">
		<div
			class="px-2 pb-1.5 pt-2 text-[11px] font-semibold uppercase tracking-[0.07em] text-[var(--st-faint)]"
		>
			{$i18n.t('Published')} · {sites.length}
		</div>
		{#each sites as s (s.id)}
			<button
				type="button"
				class="flex w-full flex-col gap-0.5 rounded-[10px] border px-2.5 py-2 text-left transition-colors duration-150
					{s.id === selectedId && !creating
					? 'border-[color-mix(in_oklab,var(--st-accent)_25%,transparent)] bg-[var(--st-accent-soft)]'
					: 'border-transparent'}"
				onclick={() => onSelect(s.id)}
			>
				<span class="flex min-w-0 items-center gap-1.5">
					<span class="st-dot {siteAccessLevel(s) === 'private' ? 'st-dot-off' : ''}"></span>
					<span
						class="truncate text-[13.5px] font-semibold {s.id === selectedId && !creating
							? 'text-[var(--st-accent-soft-ink)]'
							: ''}">{s.name}</span
					>
					<span class="st-chip ml-auto {siteAccessLevel(s) === 'public' ? 'st-chip-pub' : ''}"
						>{levelBadge(s)}</span
					>
				</span>
				<span class="font-mono text-[11.5px] text-[var(--st-faint)]">/sites/{s.slug}</span>
				{#if showAll && s.user_name}
					<span class="text-[10px] text-[var(--st-faint)]">{s.user_name}</span>
				{/if}
			</button>
		{/each}
	</nav>
</aside>
