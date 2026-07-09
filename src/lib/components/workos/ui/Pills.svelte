<script lang="ts">
	// Thin compatibility shell: same external API (priority/status/label/size)
	// call sites already depend on, but internals now delegate to the canonical
	// primitives — kills the lowercase-raw-enum priority pill and the ad hoc
	// status-dot/label recipes. `size` only affects the status pill (StatusBadge
	// supports sm/md); priority and label pills have one canonical rendering.
	import PriorityFlag from './PriorityFlag.svelte';
	import StatusBadge from './StatusBadge.svelte';
	import LabelChip from './LabelChip.svelte';
	import type { TaskPriority, TaskStatus, Label } from '../lib/types';

	export let priority: TaskPriority | null | undefined = undefined;
	export let status: TaskStatus | undefined = undefined;
	export let label: Label | undefined = undefined;
	export let size: 'sm' | 'md' = 'sm';
</script>

{#if priority !== undefined && priority !== null}
	<PriorityFlag {priority} />
{/if}
{#if status}
	<StatusBadge {status} {size} />
{/if}
{#if label}
	<LabelChip name={label.name} color={label.color} />
{/if}
