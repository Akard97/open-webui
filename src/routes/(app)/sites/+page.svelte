<script lang="ts">
	import SitesPage from '$lib/components/sites/SitesPage.svelte';
	import { WEBUI_NAME } from '$lib/stores';
</script>

<svelte:head>
	<title>Sites • {$WEBUI_NAME}</title>
</svelte:head>

<SitesPage />
