<script lang="ts">
	import { LinkPreview as LinkPreviewPrimitive } from "bits-ui";

	let { ...restProps }: LinkPreviewPrimitive.PortalProps = $props();
</script>

<LinkPreviewPrimitive.Portal {...restProps} />
