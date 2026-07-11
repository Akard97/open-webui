<script lang="ts">
	import { getContext } from 'svelte';
	import { WEBUI_NAME } from '$lib/stores';

	const i18n = getContext('i18n');
</script>

<svelte:head>
	<title>
		{$i18n.t('Home')} • {$WEBUI_NAME}
	</title>
</svelte:head>

<div class="w-full h-screen max-h-[100dvh] overflow-y-auto">
	<slot />
</div>
