<script lang="ts">
	// Canonical label chip. Two renderings sharing one shell:
	// - name + color: dot + label name
	// - count: overflow variant ("+N"), no dot — for "+3 more" style summaries.
	export let name: string = '';
	export let color: string = '';
	export let count: number | undefined = undefined;
</script>

<span
	class="inline-flex items-center gap-[5px] rounded-full bg-gray-100 dark:bg-gray-800 text-[11px] font-medium px-2 py-0.5 text-gray-700 dark:text-gray-300"
>
	{#if count !== undefined}
		+{count}
	{:else}
		<span class="w-1.5 h-1.5 rounded-full flex-none" style="background:{color}"></span>
		{name}
	{/if}
</span>
