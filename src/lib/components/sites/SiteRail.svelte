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
	class="flex flex-none flex-col border-b border-gray-100 dark:border-gray-850 md:w-72 md:border-b-0 md:border-r"
>
	<div class="flex flex-col gap-2 px-3 pb-2 pt-3">
		<button
			type="button"
			class="st-press flex h-9 items-center justify-center gap-1.5 rounded-lg bg-gray-900 text-sm font-medium text-white hover:bg-gray-800 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-200"
			onclick={onCreate}
		>
			＋ {$i18n.t('New site')}
		</button>
		{#if isAdmin}
			<div class="flex rounded-lg bg-gray-100 p-0.5 text-xs dark:bg-gray-850">
				{#each [[false, $i18n.t('My sites')], [true, $i18n.t('All users')]] as [value, label] (label)}
					<button
						type="button"
						class="flex-1 rounded-md px-2 py-1 font-medium transition-colors duration-150
							{showAll === value
							? 'bg-white text-gray-800 shadow-sm dark:bg-gray-900 dark:text-gray-100'
							: 'text-gray-500 dark:text-gray-400'}"
						onclick={() => onToggleAll(value as boolean)}>{label}</button
					>
				{/each}
			</div>
		{/if}
	</div>
	<nav class="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 pb-3 pt-1">
		<div class="px-2 pb-1.5 pt-2 text-xs font-medium text-gray-400 dark:text-gray-500">
			{$i18n.t('Published')} · {sites.length}
		</div>
		{#each sites as s (s.id)}
			<button
				type="button"
				class="flex w-full flex-col gap-0.5 rounded-lg px-2.5 py-2 text-left transition-colors duration-150
					{s.id === selectedId && !creating
					? 'bg-gray-100 dark:bg-gray-850'
					: 'hover:bg-gray-50 dark:hover:bg-gray-900'}"
				onclick={() => onSelect(s.id)}
			>
				<span class="flex min-w-0 items-center gap-1.5">
					<span class="st-dot {siteAccessLevel(s) === 'private' ? 'st-dot-off' : ''}"></span>
					<span class="truncate text-sm font-medium">{s.name}</span>
					<span class="st-chip ml-auto {siteAccessLevel(s) === 'public' ? 'st-chip-pub' : ''}"
						>{levelBadge(s)}</span
					>
				</span>
				<span class="truncate pl-3 text-xs text-gray-400 dark:text-gray-500">/sites/{s.slug}</span>
				{#if showAll && s.user_name}
					<span class="pl-3 text-[10px] text-gray-400 dark:text-gray-500">{s.user_name}</span>
				{/if}
			</button>
		{/each}
	</nav>
</aside>
