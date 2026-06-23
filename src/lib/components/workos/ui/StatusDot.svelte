<script lang="ts">
	// State-shaped status glyph: hollow ring (not started) → half-filled pie
	// (in progress) → filled check/x circle (resolved). Mirrors the board mock.
	export let shape: 'dashed' | 'ring' | 'half' | 'check' | 'x' = 'ring';
	export let color = '#9ca3af';
	export let size = 14;
</script>

<svg
	width={size}
	height={size}
	viewBox="0 0 16 16"
	fill="none"
	style="flex:none;display:block"
	aria-hidden="true"
>
	{#if shape === 'check'}
		<circle cx="8" cy="8" r="7" fill={color} />
		<path
			d="M5 8.2l2 2 4-4.4"
			fill="none"
			stroke="#fff"
			stroke-width="1.6"
			stroke-linecap="round"
			stroke-linejoin="round"
		/>
	{:else if shape === 'x'}
		<circle cx="8" cy="8" r="7" fill={color} />
		<path d="M5.5 5.5l5 5M10.5 5.5l-5 5" fill="none" stroke="#fff" stroke-width="1.6" stroke-linecap="round" />
	{:else if shape === 'half'}
		<circle cx="8" cy="8" r="6.25" fill="none" stroke={color} stroke-width="1.6" />
		<path d="M8 1.75A6.25 6.25 0 0 1 8 14.25Z" fill={color} />
	{:else if shape === 'dashed'}
		<circle cx="8" cy="8" r="6.25" fill="none" stroke={color} stroke-width="1.6" stroke-dasharray="2.4 2.4" />
	{:else}
		<circle cx="8" cy="8" r="6.25" fill="none" stroke={color} stroke-width="1.6" />
	{/if}
</svg>
