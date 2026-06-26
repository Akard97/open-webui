<script lang="ts">
	import { initials, displayName } from '../lib/store';

	export let ids: string[] = [];
	export let max = 4;
	export let size = 24; // px

	$: shown = (ids ?? []).slice(0, max);
	$: overflow = Math.max(0, (ids ?? []).length - shown.length);
	$: fontSize = Math.round(size * 0.42);
</script>

{#if (ids ?? []).length}
	<div class="flex items-center -space-x-1.5">
		{#each shown as id (id)}
			<span
				title={displayName(id)}
				class="rounded-full ring-2 ring-white dark:ring-gray-950 bg-brand-100 text-brand-700 dark:bg-brand-900 dark:text-brand-200 font-semibold inline-flex items-center justify-center flex-none"
				style="width:{size}px;height:{size}px;font-size:{fontSize}px"
			>{initials(id)}</span>
		{/each}
		{#if overflow}
			<span
				title={(ids ?? []).slice(max).map((id) => displayName(id)).join(', ')}
				class="rounded-full ring-2 ring-white dark:ring-gray-950 bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-200 font-semibold inline-flex items-center justify-center flex-none"
				style="width:{size}px;height:{size}px;font-size:{fontSize}px"
			>+{overflow}</span>
		{/if}
	</div>
{/if}
