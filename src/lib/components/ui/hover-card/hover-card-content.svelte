<script lang="ts">
	import { LinkPreview as LinkPreviewPrimitive } from "bits-ui";
	import { cn } from "$lib/components/ui/utils.js";
	import HoverCardPortal from "./hover-card-portal.svelte";
	import type { ComponentProps } from "svelte";
	import type { WithoutChildrenOrChild } from "$lib/components/ui/utils.js";

	let {
		ref = $bindable(null),
		class: className,
		sideOffset = 6,
		side = "right",
		align = "start",
		children,
		portalProps,
		...restProps
	}: LinkPreviewPrimitive.ContentProps & {
		portalProps?: WithoutChildrenOrChild<ComponentProps<typeof HoverCardPortal>>;
	} = $props();
</script>

<HoverCardPortal {...portalProps}>
	<LinkPreviewPrimitive.Content
		bind:ref
		data-slot="hover-card-content"
		{sideOffset}
		{side}
		{align}
		class={cn(
			"data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 bg-popover text-popover-foreground z-[70] w-64 origin-(--bits-floating-transform-origin) rounded-md border p-4 shadow-md outline-hidden",
			className
		)}
		{...restProps}
	>
		{@render children?.()}
	</LinkPreviewPrimitive.Content>
</HoverCardPortal>
