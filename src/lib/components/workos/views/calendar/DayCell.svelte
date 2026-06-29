<script lang="ts">
	export let date: Date;
	export let dimmed = false;
	export let today = false;
</script>

<div class="flex flex-col min-h-[88px] p-1.5 border-r border-b border-gray-100 dark:border-gray-900">
	{#if today}
		<span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-primary text-primary-foreground text-xs font-medium">{date.getDate()}</span>
	{:else}
		<span class="text-xs {dimmed ? 'text-gray-300 dark:text-gray-700' : 'text-gray-500 dark:text-gray-400'}">{date.getDate()}</span>
	{/if}
</div>
