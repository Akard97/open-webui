<script lang="ts">
	import { getContext } from 'svelte';
	import CloudArrowUp from '$lib/components/icons/CloudArrowUp.svelte';

	const i18n = getContext('i18n');

	let {
		label,
		sublabel = '',
		onFiles
	}: { label: string; sublabel?: string; onFiles: (files: File[]) => void } = $props();

	let dragging = $state(false);
	let inputEl: HTMLInputElement | undefined = $state();
</script>

<button
	type="button"
	class="w-full rounded-xl border-[1.5px] border-dashed px-6 py-6 text-center transition-colors duration-150
		{dragging
		? 'border-[var(--st-accent)] bg-[var(--st-accent-soft)]'
		: 'border-[var(--st-border)] hover:border-[var(--st-faint)]'}"
	ondragover={(e) => {
		e.preventDefault();
		dragging = true;
	}}
	ondragleave={() => (dragging = false)}
	ondrop={(e) => {
		e.preventDefault();
		dragging = false;
		onFiles(Array.from(e.dataTransfer?.files ?? []));
	}}
	onclick={() => inputEl?.click()}
>
	<span
		class="mx-auto mb-2.5 flex h-9 w-9 items-center justify-center rounded-[10px] bg-[var(--st-accent-soft)]"
	>
		<CloudArrowUp
			className="w-[18px] h-[18px] text-[var(--st-accent-soft-ink)]"
			strokeWidth="1.8"
		/>
	</span>
	<span class="block text-[13.5px] font-semibold text-[var(--st-ink)]">{label}</span>
	{#if sublabel}
		<span class="mt-0.5 block text-xs text-[var(--st-faint)]">{sublabel}</span>
	{/if}
</button>
<input
	bind:this={inputEl}
	type="file"
	multiple
	hidden
	aria-label={$i18n.t('Choose files')}
	onchange={(e) => {
		const t = e.target as HTMLInputElement;
		onFiles(Array.from(t.files ?? []));
		t.value = '';
	}}
/>
