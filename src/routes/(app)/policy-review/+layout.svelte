<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { showSidebar } from '$lib/stores';
	import '$lib/components/policy-review/styles.css';

	let { children } = $props();

	// OWUI's chat sidebar is global; suppress it while the user is inside the
	// Policy Review tool so the design's own internal sidebar isn't covered.
	// Restore the prior visibility when navigating away.
	let prev: boolean | undefined;
	onMount(() => {
		showSidebar.update((v) => {
			prev = v;
			return false;
		});
	});
	onDestroy(() => {
		if (prev !== undefined) showSidebar.set(prev);
	});
</script>

<div class="pr-root w-full h-full">
	{@render children()}
</div>
