<script lang="ts">
	import type { Snippet } from 'svelte';

	type Tone = 'ok' | 'bad' | 'warn' | 'info' | 'muted' | 'default';

	let {
		tone = 'default',
		active = false,
		onclick,
		children
	}: {
		tone?: Tone;
		active?: boolean;
		onclick?: () => void;
		children?: Snippet;
	} = $props();
</script>

<button class="chip apx-tone-{tone}" class:active {onclick} type="button">
	{#if children}
		{@render children()}
	{/if}
</button>
