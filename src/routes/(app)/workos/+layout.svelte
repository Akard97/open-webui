<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { showSidebar } from '$lib/stores';

	let { children } = $props();

	// OWUI's chat sidebar is global; suppress it while the user is inside the
	// WorkOS tool so it gets the full content area (mirrors the Policy Review
	// layout). Restore the prior visibility when navigating away.
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

<div class="w-full h-full">
	{@render children()}
</div>
