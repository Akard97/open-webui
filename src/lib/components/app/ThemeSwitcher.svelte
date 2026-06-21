<script lang="ts">
	import { getContext } from 'svelte';

	import { theme } from '$lib/stores';
	import { setTheme, resolveMode, prefersSystemDark } from '$lib/utils/theme';

	import Sun from '$lib/components/icons/Sun.svelte';
	import Moon from '$lib/components/icons/Moon.svelte';

	const i18n = getContext<any>('i18n');

	// The mode currently showing: 'system' resolves to the OS preference,
	// 'oled-dark' counts as 'dark'. Re-runs whenever $theme changes.
	$: mode = resolveMode($theme, prefersSystemDark());

	const select = (next: 'light' | 'dark') => setTheme(next);
	const toggle = () => select(mode === 'dark' ? 'light' : 'dark');
</script>

<div class="shrink-0 px-2 py-2 border-t border-gray-200/70 dark:border-gray-900">
	<!-- Collapsed: single toggle button (icon = current mode) -->
	<button
		type="button"
		on:click={toggle}
		aria-label={$i18n?.t('Toggle theme') ?? 'Toggle theme'}
		class="flex group-hover/rail:hidden w-full h-9 items-center rounded-lg
			text-gray-600 dark:text-gray-400 hover:bg-gray-200/40 dark:hover:bg-gray-900/60
			hover:text-gray-900 dark:hover:text-white transition-colors duration-100"
	>
		<span class="w-10 shrink-0 flex items-center justify-center">
			{#if mode === 'dark'}
				<Moon className="size-[1.125rem]" strokeWidth="1.5" />
			{:else}
				<Sun className="size-[1.125rem]" strokeWidth="1.5" />
			{/if}
		</span>
	</button>

	<!-- Expanded: 2-segment Light/Dark pill -->
	<div
		role="group"
		aria-label={$i18n?.t('Theme') ?? 'Theme'}
		class="hidden group-hover/rail:flex gap-1 p-1 rounded-lg bg-gray-200/60 dark:bg-gray-900"
	>
		<button
			type="button"
			on:click={() => select('light')}
			aria-pressed={mode === 'light'}
			class="flex-1 flex items-center justify-center gap-1.5 h-7 rounded-md text-[12px] font-medium
				transition-colors duration-100
				{mode === 'light'
					? 'bg-white text-gray-900 shadow-sm'
					: 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'}"
		>
			<Sun className="size-4" strokeWidth="1.5" />
			<span>{$i18n?.t('Light') ?? 'Light'}</span>
		</button>
		<button
			type="button"
			on:click={() => select('dark')}
			aria-pressed={mode === 'dark'}
			class="flex-1 flex items-center justify-center gap-1.5 h-7 rounded-md text-[12px] font-medium
				transition-colors duration-100
				{mode === 'dark'
					? 'bg-gray-700 text-white shadow-sm'
					: 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'}"
		>
			<Moon className="size-4" strokeWidth="1.5" />
			<span>{$i18n?.t('Dark') ?? 'Dark'}</span>
		</button>
	</div>
</div>
