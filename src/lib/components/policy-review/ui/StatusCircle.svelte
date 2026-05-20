<script lang="ts">
	import Icon from './Icon.svelte';
	import type { ItemResult } from '../lib/types';

	let { result, size = 18 }: { result: ItemResult; size?: number } = $props();
</script>

{#if result === 'compliant'}
	<span class="status-circle ok" style="width:{size}px;height:{size}px">
		<Icon name="check" size={size * 0.6} stroke={3} />
	</span>
{:else if result === 'non-compliant'}
	<span class="status-circle bad" style="width:{size}px;height:{size}px">
		<Icon name="x" size={size * 0.6} stroke={3} />
	</span>
{:else if result === 'human'}
	<span class="status-circle warn" style="width:{size}px;height:{size}px">
		<Icon name="user" size={size * 0.55} stroke={2.5} />
	</span>
{:else}
	<span class="status-circle pending" style="width:{size}px;height:{size}px"></span>
{/if}
