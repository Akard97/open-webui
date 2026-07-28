<script lang="ts">
	export let src: string;
	export let alt = '';
	export let onClose: () => void;

	function onKeydown(e: KeyboardEvent): void {
		if (e.key === 'Escape') {
			e.stopPropagation(); // keep the task drawer open
			onClose();
		}
	}
</script>

<svelte:window on:keydown|capture={onKeydown} />

<!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
<div
	class="fixed inset-0 z-[100] flex items-center justify-center bg-black/75 p-6"
	onclick={(e) => { e.stopPropagation(); onClose(); }}
	role="dialog" aria-modal="true" aria-label={alt || 'Image preview'}
>
	<img
		{src} {alt}
		class="max-h-full max-w-full rounded-xl object-contain shadow-2xl"
		onclick={(e) => e.stopPropagation()}
	/>
	<button
		class="absolute right-4 top-4 flex size-9 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20"
		title="Close" onclick={(e) => { e.stopPropagation(); onClose(); }}
	>✕</button>
</div>
