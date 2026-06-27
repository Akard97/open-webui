<script lang="ts">
	import { PRIORITY_COLOR } from '../../lib/colors';
	import type { TaskPriority } from '../../lib/types';
	export let priority: TaskPriority | null | undefined = null;
	export let size = 15;

	$: color = priority ? PRIORITY_COLOR[priority] : '#9ca3af';
	// Ascending signal bars; the number "lit" encodes the level.
	$: level = priority === 'high' ? 3 : priority === 'medium' ? 2 : priority === 'low' ? 1 : 0;
	const bars = [
		{ x: 3, y: 13, h: 7 },
		{ x: 10, y: 8, h: 12 },
		{ x: 17, y: 3, h: 17 }
	];
</script>

{#if priority === 'urgent'}
	<span class="inline-flex items-center justify-center rounded-[3px] flex-none" style="width:{size}px;height:{size}px;background:{color}" title="Urgent">
		<svg width={size - 4} height={size - 4} viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3.2" stroke-linecap="round" aria-hidden="true">
			<path d="M12 6v7" /><path d="M12 17.5h.01" />
		</svg>
	</span>
{:else}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" class="flex-none" aria-hidden="true">
		{#each bars as b, i}
			<rect x={b.x} y={b.y} width="4" height={b.h} rx="1" fill={color} opacity={i < level ? 1 : 0.28} />
		{/each}
	</svg>
{/if}
