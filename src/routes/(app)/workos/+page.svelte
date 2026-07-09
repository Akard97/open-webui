<script lang="ts">
	import WorkOSApp from '$lib/components/workos/WorkOSApp.svelte';
	import { WEBUI_NAME } from '$lib/stores';
</script>

<svelte:head>
	<title>WorkOS • {$WEBUI_NAME}</title>
</svelte:head>

<WorkOSApp />
