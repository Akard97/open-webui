<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import { validateWidget, type Widget } from '$lib/utils/widgets';
	import { copyToClipboard } from '$lib/utils';

	import CodeBlock from '$lib/components/chat/Messages/CodeBlock.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import DocumentDuplicate from '$lib/components/icons/DocumentDuplicate.svelte';

	import WidgetChart from './WidgetChart.svelte';
	import WidgetKpi from './WidgetKpi.svelte';
	import WidgetCards from './WidgetCards.svelte';
	import WidgetTable from './WidgetTable.svelte';
	import WidgetTimeline from './WidgetTimeline.svelte';
	import WidgetButtons from './WidgetButtons.svelte';
	import WidgetForm from './WidgetForm.svelte';
	import WidgetHtml from './WidgetHtml.svelte';

	export let id: string;
	export let token: any;
	export let done = true;

	let showSource = false;
	let copied = false;

	// A fence is renderable once its closing ``` has streamed in; if the
	// response is done and the model forgot to close the fence, render anyway.
	$: complete = (token?.raw ?? '').slice(-4).includes('```') || done;

	$: isHtml = token?.lang === 'widget-html';

	let widget: Widget | null = null;
	let parseError: string | null = null;
	let parsedText: string | null = null;

	$: if (complete && !isHtml) {
		parseWidget(token?.text ?? '');
	}

	const parseWidget = (text: string) => {
		// Streaming re-lexes the message on every tick, handing us a fresh token
		// object with identical text; bail out so `widget` keeps its identity and
		// downstream components (vega chart) don't re-render per tick.
		if (text === parsedText) return;
		parsedText = text;
		try {
			const validation = validateWidget(JSON.parse(text));
			if (validation.ok) {
				widget = validation.widget;
				parseError = null;
			} else {
				widget = null;
				parseError = validation.error;
			}
		} catch (error) {
			widget = null;
			parseError = error instanceof Error ? error.message : String(error);
		}
	};

	// Peek at the streaming payload to pick a matching skeleton shape.
	$: peekedType = (token?.text ?? '').match(/"type"\s*:\s*"(\w+)"/)?.[1] ?? null;

	const copySource = async () => {
		copied = true;
		await copyToClipboard(token?.text ?? '');
		setTimeout(() => {
			copied = false;
		}, 1000);
	};
</script>

<div class="relative group/widget my-1.5 w-full" dir="auto">
	{#if !complete}
		<!-- Streaming skeleton: never show raw JSON mid-stream -->
		<div
			class="animate-pulse rounded-2xl border border-gray-100/50 dark:border-gray-850/50 bg-gray-50/80 dark:bg-gray-850/40 p-4"
		>
			{#if peekedType === 'kpi'}
				<div class="grid grid-cols-3 gap-3">
					{#each Array(3) as _}
						<div class="h-20 rounded-xl bg-gray-200/60 dark:bg-gray-800/60"></div>
					{/each}
				</div>
			{:else if peekedType === 'chart'}
				<div class="h-9 w-40 rounded-lg bg-gray-200/60 dark:bg-gray-800/60 mb-3"></div>
				<div class="flex items-end gap-2 h-32">
					{#each [40, 70, 55, 90, 65, 80] as h}
						<div
							class="flex-1 rounded-t-lg bg-gray-200/60 dark:bg-gray-800/60"
							style="height: {h}%"
						></div>
					{/each}
				</div>
			{:else}
				<div class="h-5 w-1/3 rounded-lg bg-gray-200/60 dark:bg-gray-800/60 mb-3"></div>
				<div class="h-4 w-full rounded-lg bg-gray-200/60 dark:bg-gray-800/60 mb-2"></div>
				<div class="h-4 w-2/3 rounded-lg bg-gray-200/60 dark:bg-gray-800/60"></div>
			{/if}
		</div>
	{:else if isHtml}
		<WidgetHtml {id} html={token?.text ?? ''} />
	{:else if parseError}
		<!-- Invalid payload: graceful fallback, never a broken UI -->
		<div
			class="text-xs px-3 py-2 mb-1 rounded-xl border border-red-600/10 bg-red-600/5 text-red-600 dark:text-red-400"
		>
			{$i18n.t('Failed to render widget')}: {parseError}
		</div>
		<CodeBlock {id} {token} lang="json" code={token?.text ?? ''} run={false} edit={false} />
	{:else if widget}
		{#if showSource}
			<CodeBlock {id} {token} lang="json" code={token?.text ?? ''} run={false} edit={false} />
		{:else if widget.type === 'chart'}
			<WidgetChart {widget} />
		{:else if widget.type === 'kpi'}
			<WidgetKpi {widget} />
		{:else if widget.type === 'cards'}
			<WidgetCards {id} {widget} {done} />
		{:else if widget.type === 'table'}
			<WidgetTable {widget} />
		{:else if widget.type === 'timeline'}
			<WidgetTimeline {widget} />
		{:else if widget.type === 'buttons'}
			<WidgetButtons {widget} {done} />
		{:else if widget.type === 'form'}
			<WidgetForm {widget} {done} />
		{/if}

		<!-- Hover chrome: view source + copy -->
		<div
			class="absolute -top-2 end-1 z-10 invisible group-hover/widget:visible flex gap-0.5 rounded-lg bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-850 px-1 py-0.5 shadow-xs"
		>
			<Tooltip content={showSource ? $i18n.t('Show widget') : $i18n.t('View source')}>
				<button
					class="p-1 rounded-md hover:bg-black/5 dark:hover:bg-white/5 transition text-gray-500 dark:text-gray-400"
					on:click={() => {
						showSource = !showSource;
					}}
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						class="size-3.5"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M17.25 6.75 22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3-4.5 16.5"
						/>
					</svg>
				</button>
			</Tooltip>
			<Tooltip content={copied ? $i18n.t('Copied') : $i18n.t('Copy')}>
				<button
					class="p-1 rounded-md hover:bg-black/5 dark:hover:bg-white/5 transition text-gray-500 dark:text-gray-400"
					on:click={copySource}
				>
					{#if copied}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							fill="none"
							viewBox="0 0 24 24"
							stroke-width="1.5"
							stroke="currentColor"
							class="size-3.5 text-green-500"
						>
							<path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5" />
						</svg>
					{:else}
						<DocumentDuplicate className="size-3.5" strokeWidth="1.5" />
					{/if}
				</button>
			</Tooltip>
		</div>
	{/if}
</div>
