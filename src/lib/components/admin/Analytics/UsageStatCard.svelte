<script lang="ts">
	export let label: string;
	export let value: string;
	export let delta: { dir: 'up' | 'down' | 'flat'; pct: number | null } | null = null;
	export let sub: string = '';
	export let clickable: boolean = false;
</script>

<svelte:element
	this={clickable ? 'button' : 'div'}
	type={clickable ? 'button' : undefined}
	class="border border-gray-50 dark:border-gray-850 rounded-lg px-3 py-2 text-left w-full {clickable
		? 'cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-850 transition-colors'
		: ''}"
	on:click
>
	<div class="text-xs text-gray-500 dark:text-gray-400 mb-1 truncate">{label}</div>
	<div class="flex items-baseline gap-2">
		<div class="text-xl font-medium text-gray-900 dark:text-white">{value}</div>
		{#if delta}
			<span
				class="text-xs {delta.dir === 'up'
					? 'text-green-600 dark:text-green-400'
					: delta.dir === 'down'
						? 'text-red-600 dark:text-red-400'
						: 'text-gray-400'}"
			>
				{delta.dir === 'up' ? '▲' : delta.dir === 'down' ? '▼' : '—'}{delta.pct !== null
					? ` ${Math.abs(delta.pct)}%`
					: ''}
			</span>
		{/if}
	</div>
	{#if sub}
		<div class="text-xs text-gray-400 mt-0.5 truncate">{sub}</div>
	{/if}
</svelte:element>
