<script lang="ts">
	import { LinkPreview as LinkPreviewPrimitive } from "bits-ui";

	let { open = $bindable(false), ...restProps }: LinkPreviewPrimitive.RootProps = $props();
</script>

<LinkPreviewPrimitive.Root bind:open {...restProps} />
