<script lang="ts">
	// Canonical priority glyph: flag icon (fixed 14px — kills the 13/14/15 size
	// drift) + optional Title-case label. Icon.svelte's flag path only draws
	// cleanly in its default stroke/outline style (fill="none"): the pole is a
	// separate <line>, which has no fill, so passing fill="currentColor" would
	// render a filled flag head with an invisible pole. So both the "has a
	// priority" and "no priority" states use the same outline glyph, just
	// recolored — PRIORITY_COLOR[priority] vs. the muted PRIORITY_NONE gray.
	import Icon from './Icon.svelte';
	import type { TaskPriority } from '../lib/types';
	import { PRIORITY_COLOR, PRIORITY_LABEL, PRIORITY_NONE } from '../lib/colors';

	export let priority: TaskPriority | null | undefined = undefined;
	export let showLabel: boolean = true;

	$: hasPriority = priority !== null && priority !== undefined;
	$: color = hasPriority ? PRIORITY_COLOR[priority as TaskPriority] : PRIORITY_NONE;
	$: label = hasPriority ? PRIORITY_LABEL[priority as TaskPriority] : '—';
</script>

<span class="inline-flex items-center gap-1.5">
	<span class="flex-none" style="color:{color}"><Icon name="flag" size={14} /></span>
	{#if showLabel}
		<span class="text-[12px] font-medium {hasPriority ? '' : 'text-gray-400 dark:text-gray-500'}">{label}</span>
	{/if}
</span>
