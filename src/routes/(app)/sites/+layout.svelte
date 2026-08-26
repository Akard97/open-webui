<script lang="ts">
	import { goto } from '$app/navigation';
	import { user } from '$lib/stores';
	import { canSeeSites } from '$lib/components/sites/lib/visibility';

	let { children } = $props();

	// Route guard: same predicate as the rail item, so a deep link can't
	// reach a tool the rail wouldn't show.
	let allowed = $derived(canSeeSites({ user: $user }));
	$effect(() => {
		if (!allowed) goto('/home');
	});
</script>

{#if allowed}
	{@render children()}
{/if}
