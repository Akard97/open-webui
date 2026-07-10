<script lang="ts">
	// Canonical KPI numeral: the .wos-display step (28px/700 tabular, styles.css)
	// with an optional DeltaBadge on the baseline. Absorbs the 16/22/34px trio.
	import DeltaBadge from './DeltaBadge.svelte';

	export let value: string | number;
	export let delta: { up: boolean; text: string; positive?: boolean } | null = null;
</script>

<span class="inline-flex items-baseline gap-1.5">
	<span class="wos-display text-gray-900 dark:text-gray-100">{value}</span>
	{#if delta}
		<DeltaBadge up={delta.up} text={delta.text} positive={delta.positive ?? null} />
	{/if}
</span>
