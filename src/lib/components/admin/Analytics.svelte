<script>
	import { onMount, getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { user } from '$lib/stores';

	import Dashboard from './Analytics/Dashboard.svelte';
	import Usage from './Analytics/Usage.svelte';

	const i18n = getContext('i18n');

	let loaded = false;
	let tab = 'models';

	onMount(async () => {
		if ($user?.role !== 'admin') {
			await goto('/');
		}
		loaded = true;
	});
</script>

{#if loaded}
	<div class="w-full h-full pb-2 px-[16px]">
		<div class="flex gap-3 mb-2">
			<button
				class="min-w-fit p-1.5 {tab === 'models' ? '' : 'text-gray-300 dark:text-gray-600'}"
				on:click={() => (tab = 'models')}>{$i18n.t('Models')}</button
			>
			<button
				class="min-w-fit p-1.5 {tab === 'usage' ? '' : 'text-gray-300 dark:text-gray-600'}"
				on:click={() => (tab = 'usage')}>{$i18n.t('Usage')}</button
			>
		</div>
		{#if tab === 'models'}
			<Dashboard />
		{:else}
			<Usage />
		{/if}
	</div>
{/if}
