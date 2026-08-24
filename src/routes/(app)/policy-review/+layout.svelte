<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { showSidebar, user, config } from '$lib/stores';
	import { canSeePolicyReview } from '$lib/components/policy-review/lib/visibility';
	import '$lib/components/policy-review/styles.css';

	let { children } = $props();

	// Route guard: same predicate as the rail item, so a deep link can't
	// reach a tool the rail wouldn't show. Reactive so a config refresh
	// that turns the flag off also ejects the user.
	let allowed = $derived(canSeePolicyReview({ user: $user, config: $config }));
	$effect(() => {
		if (!allowed) goto('/home');
	});

	// OWUI's chat sidebar is global; suppress it while the user is inside the
	// Policy Review tool so the design's own internal sidebar isn't covered.
	// Restore the prior visibility when navigating away.
	let prev: boolean | undefined;
	onMount(() => {
		if (!allowed) return; // being redirected away — don't flicker the sidebar
		showSidebar.update((v) => {
			prev = v;
			return false;
		});
	});
	onDestroy(() => {
		if (prev !== undefined) showSidebar.set(prev);
	});
</script>

{#if allowed}
	<div class="pr-root w-full h-full">
		{@render children()}
	</div>
{/if}
