<script lang="ts">
	// Canonical empty state (spec §4, Timeline anatomy = the canon).
	// block = view-level: icon tile + line + optional sub + optional CTA.
	// quiet = one caption line with the em-dash placeholder glyph, for card rails.
	import Icon from './Icon.svelte';
	import { Button } from '$lib/components/ui/button';

	export let title: string;
	export let variant: 'block' | 'quiet' = 'block';
	export let icon = '';
	export let sub = '';
	export let ctaLabel = '';
	export let onCta: (() => void) | null = null;
</script>

{#if variant === 'quiet'}
	<div class="py-1 text-xs text-gray-400 dark:text-gray-500">— {title}</div>
{:else}
	<div class="flex flex-col items-center gap-2.5 px-6 py-10 text-center">
		{#if icon}
			<span class="flex h-12 w-12 items-center justify-center rounded-2xl bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500">
				<Icon name={icon} size={24} />
			</span>
		{/if}
		<span class="text-sm text-gray-500 dark:text-gray-400">{title}</span>
		{#if sub}<span class="max-w-[40ch] text-xs text-gray-400 dark:text-gray-500">{sub}</span>{/if}
		{#if ctaLabel && onCta}
			<Button size="sm" class="mt-1" onclick={onCta}><Icon name="plus" size={15} /> {ctaLabel}</Button>
		{/if}
	</div>
{/if}
