<script lang="ts">
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	let {
		label,
		onFiles
	}: { label: string; onFiles: (files: File[]) => void } = $props();

	let dragging = $state(false);
	let inputEl: HTMLInputElement | undefined = $state();
</script>

<button
	type="button"
	class="w-full rounded-xl border-[1.5px] border-dashed px-6 py-7 text-center text-[13px] transition-colors duration-150
		{dragging
		? 'border-[var(--st-accent)] bg-[var(--st-accent-soft)] text-[var(--st-accent-soft-ink)]'
		: 'border-[var(--st-border)] text-[var(--st-muted)]'}"
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
	{label}
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
