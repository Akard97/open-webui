<script lang="ts">
	import { getContext } from 'svelte';
	import { marked } from 'marked';

	import { PALETTE, DEFAULT_COLOR_CYCLE, type CardsWidget } from '$lib/utils/widgets';
	import MarkdownTokens from '$lib/components/chat/Messages/Markdown/MarkdownTokens.svelte';

	const i18n = getContext('i18n');

	export let id: string;
	export let widget: CardsWidget;
	export let done = true;

	const widgetActions: { submit: (prompt: string) => void } | undefined =
		getContext('widgetActions');

	// Card actions are alternatives: picking one locks the widget.
	let submitted = false;

	$: columns = widget.columns ?? (widget.items.length > 1 ? 2 : 1);
	$: gridCols =
		columns === 1 ? 'grid-cols-1' : columns === 2 ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1 sm:grid-cols-3';
</script>

<div class="grid {gridCols} gap-2.5 w-full">
	{#each widget.items as item, idx}
		{@const palette = PALETTE[item.color ?? DEFAULT_COLOR_CYCLE[idx % DEFAULT_COLOR_CYCLE.length]]}
		<div
			class="relative flex flex-col overflow-hidden rounded-2xl border border-gray-100 dark:border-gray-850 bg-white dark:bg-gray-900 shadow-sm"
		>
			<!-- gradient accent bar -->
			<div class="h-1 w-full bg-gradient-to-r {palette.accent}"></div>

			<div class="flex flex-col grow p-4">
				<div class="flex items-start justify-between gap-2">
					<div class="min-w-0">
						<div class="font-semibold text-[#00313f] dark:text-gray-50 leading-snug">
							{item.title}
						</div>
						{#if item.subtitle}
							<div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
								{item.subtitle}
							</div>
						{/if}
					</div>
					{#if item.badge}
						<span
							class="shrink-0 rounded-full px-2 py-0.5 text-[0.7rem] font-medium {palette.badge}"
						>
							{item.badge}
						</span>
					{/if}
				</div>

				{#if item.body}
					<div class="mt-2 text-sm text-gray-600 dark:text-gray-300 markdown-prose-sm">
						<MarkdownTokens
							id={`${id}-card-${idx}`}
							tokens={marked.lexer(item.body)}
							{done}
							editCodeBlock={false}
							allowEmbeds={false}
						/>
					</div>
				{/if}

				{#if item.action}
					<div class="mt-auto pt-3">
						<button
							class="w-full rounded-xl bg-gradient-to-r {palette.accent} px-3 py-1.5 text-sm font-medium text-white transition enabled:hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
							disabled={!widgetActions || !done || submitted}
							title={!widgetActions ? $i18n.t('Actions unavailable here') : ''}
							on:click={() => {
								if (submitted) return;
								submitted = true;
								widgetActions?.submit(item.action?.message ?? '');
							}}
						>
							{item.action.label}
						</button>
					</div>
				{/if}
			</div>
		</div>
	{/each}
</div>
