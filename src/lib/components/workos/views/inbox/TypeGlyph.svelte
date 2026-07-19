<script lang="ts">
	// Tinted per-type glyph: bubble (30px rounded square, feed rows) or inline (bare icon).
	// Hues: mentioned = brand primary, assigned = in-progress teal (data color),
	// commented/status = neutral gray — one meaning per hue (design system D1/D3).
	import Icon from '../../ui/Icon.svelte';
	import { STATUS_COLOR, tint } from '../../lib/colors';
	import type { NotificationType } from '../../lib/types';

	export let type: NotificationType;
	export let variant: 'bubble' | 'inline' = 'bubble';

	const ICON: Record<NotificationType, string> = {
		mentioned: 'at-sign',
		assigned: 'user-plus',
		commented: 'message-square',
		status_changed: 'arrow-right-left'
	};
	// Colored types carry an inline style; neutral ones use theme classes.
	const STYLE: Partial<Record<NotificationType, string>> = {
		mentioned: `color:var(--primary);background:${tint('var(--primary)')}`,
		assigned: `color:${STATUS_COLOR.in_progress};background:${tint(STATUS_COLOR.in_progress)}`
	};
</script>

{#if variant === 'bubble'}
	<span
		class="flex size-[30px] flex-none items-center justify-center rounded-[10px]
			{STYLE[type] ? '' : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'}"
		style={STYLE[type] ?? ''}
	>
		<Icon name={ICON[type]} size={15} />
	</span>
{:else}
	<span
		class="inline-flex flex-none items-center align-[-2px] {STYLE[type] ? '' : 'text-gray-400 dark:text-gray-500'}"
		style={STYLE[type] ? (STYLE[type] as string).split(';')[0] : ''}
	>
		<Icon name={ICON[type]} size={13} />
	</span>
{/if}
