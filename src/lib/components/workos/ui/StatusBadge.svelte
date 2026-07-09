<script lang="ts">
	// Canonical status pill: soft tinted background + StatusDot glyph + label.
	// Non-interactive display element (no hover/focus states) — read-only rendering.
	import StatusDot from './StatusDot.svelte';
	import { STATUS_LABEL, type TaskStatus } from '../lib/types';
	import { STATUS_COLOR, statusShape, tint } from '../lib/colors';

	export let status: TaskStatus;
	export let size: 'md' | 'sm' = 'md';

	$: sizeClass =
		size === 'sm'
			? 'rounded-md text-[11px] font-medium px-2 py-0.5 gap-[5px]'
			: 'rounded-lg text-[13px] font-medium px-2.5 py-1 gap-[6px]';
	$: dotSize = size === 'sm' ? 11 : 14;
</script>

<span
	class="inline-flex items-center {sizeClass}"
	style="background:{tint(STATUS_COLOR[status])}; color:{STATUS_COLOR[status]}"
>
	<StatusDot shape={statusShape(status)} color={STATUS_COLOR[status]} size={dotSize} />
	{STATUS_LABEL[status]}
</span>
