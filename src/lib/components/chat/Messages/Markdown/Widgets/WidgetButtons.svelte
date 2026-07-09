<script lang="ts">
	import { getContext } from 'svelte';
	import { BRAND_BUTTON_CLASS, type ButtonsWidget } from '$lib/utils/widgets';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	const i18n = getContext('i18n');

	export let widget: ButtonsWidget;
	export let done = true;

	const widgetActions: { submit: (prompt: string) => void } | undefined =
		getContext('widgetActions');

	let selectedIdx: number | null = null;
	let submitted = false;

	$: enabled = !!widgetActions && done && !submitted;

	const onSelect = (idx: number) => {
		if (!enabled) return;
		// One choice per widget: block re-clicks and double-clicks before the
		// submit reaches the chat.
		submitted = true;
		selectedIdx = idx;
		widgetActions?.submit(widget.items[idx].message);
	};
</script>

<div class="w-full">
	{#if widget.label}
		<div class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
			{widget.label}
		</div>
	{/if}

	<div class="flex flex-wrap gap-2">
		{#each widget.items as item, idx}
			<Tooltip content={!widgetActions ? $i18n.t('Actions unavailable here') : ''}>
				<button
					class="rounded-xl px-4 py-2 text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed
						{selectedIdx === idx
						? `${BRAND_BUTTON_CLASS} ring-2 ring-[#00a5ba]/50`
						: item.style === 'secondary'
							? 'border border-gray-200 dark:border-gray-800 text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-900 enabled:hover:bg-gray-50 dark:enabled:hover:bg-gray-850'
							: `${BRAND_BUTTON_CLASS} shadow-sm`}"
					disabled={!enabled}
					on:click={() => onSelect(idx)}
				>
					{item.label}
				</button>
			</Tooltip>
		{/each}
	</div>
</div>
