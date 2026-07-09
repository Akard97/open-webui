<script lang="ts">
	import PolicyReviewApp from '$lib/components/policy-review/PolicyReviewApp.svelte';
	import { WEBUI_NAME } from '$lib/stores';
</script>

<svelte:head>
	<title>Policy Review • {$WEBUI_NAME}</title>
</svelte:head>

<PolicyReviewApp />
