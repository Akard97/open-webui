<script lang="ts">
	import { getContext, onDestroy } from 'svelte';
	import { theme } from '$lib/stores';
	import { toVegaLiteSpec, isArcChart, type ChartWidget } from '$lib/utils/widgets';

	const i18n = getContext('i18n');

	export let widget: ChartWidget;

	let containerEl: HTMLDivElement | null = null;
	let view: any = null;
	let renderError: string | null = null;
	let rendering = false;
	let renderedWidth = 0;

	// Custom tooltip: the vega view is live (renderer: svg), values arrive via
	// the tooltip handler; rendered as a fixed-position Osool-ink card.
	let tipVisible = false;
	let tipX = 0;
	let tipY = 0;
	let tipRows: [string, string][] = [];

	const isDark = () =>
		typeof document !== 'undefined' && document.documentElement.classList.contains('dark');

	const tooltipHandler = (_view: unknown, event: MouseEvent, _item: unknown, value: unknown) => {
		if (value == null || value === '') {
			tipVisible = false;
			return;
		}
		tipRows =
			typeof value === 'object'
				? Object.entries(value as Record<string, unknown>).map(([k, v]) => [k, String(v)])
				: [['', String(value)]];
		tipX = Math.min(event.clientX + 12, window.innerWidth - 190);
		tipY = Math.min(event.clientY + 12, window.innerHeight - 80);
		tipVisible = true;
	};

	let renderPending = false;

	const render = async () => {
		if (!containerEl) return;
		if (rendering) {
			// A render is in flight; remember to run again with the latest
			// widget/theme once it finishes instead of dropping the update.
			renderPending = true;
			return;
		}
		rendering = true;
		try {
			const [vega, vegaLite] = await Promise.all([import('vega'), import('vega-lite')]);

			const available = containerEl.clientWidth || 480;
			const width = isArcChart(widget)
				? Math.min(available, 340)
				: Math.min(Math.max(available, 240), 520);
			renderedWidth = containerEl.clientWidth;

			const spec = toVegaLiteSpec(widget, isDark(), width);
			const compiled = vegaLite.compile(spec as any).spec;

			view?.finalize();
			tipVisible = false;
			view = new vega.View(vega.parse(compiled), {
				renderer: 'svg',
				container: containerEl,
				hover: true
			});
			view.tooltip(tooltipHandler);
			await view.runAsync();
			renderError = null;
		} catch (error) {
			console.error('Failed to render chart widget:', error);
			renderError = error instanceof Error ? error.message : String(error);
		} finally {
			rendering = false;
			if (renderPending) {
				renderPending = false;
				render();
			}
		}
	};

	// Re-render when the payload, theme, or container availability changes.
	$: widget, $theme, containerEl, render();

	let resizeObserver: ResizeObserver | null = null;
	$: if (containerEl && !resizeObserver && typeof ResizeObserver !== 'undefined') {
		resizeObserver = new ResizeObserver(() => {
			if (containerEl && Math.abs(containerEl.clientWidth - renderedWidth) > 32) {
				render();
			}
		});
		resizeObserver.observe(containerEl);
	}

	onDestroy(() => {
		resizeObserver?.disconnect();
		view?.finalize();
	});
</script>

<div
	class="not-prose w-full max-w-xl rounded-2xl border border-gray-100 dark:border-gray-850 bg-white dark:bg-gray-900 shadow-sm p-4"
>
	{#if widget.title}
		<div class="text-sm font-semibold text-[#00313f] dark:text-gray-50 leading-snug">
			{widget.title}
		</div>
	{/if}
	{#if widget.subtitle}
		<div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
			{widget.subtitle}
		</div>
	{/if}

	{#if renderError}
		<div
			class="mt-2 text-xs px-3 py-2 rounded-xl border border-red-600/10 bg-red-600/5 text-red-600 dark:text-red-400"
		>
			{$i18n.t('Failed to render visualization')}: {renderError}
		</div>
	{/if}

	<div
		bind:this={containerEl}
		class="mt-2 flex justify-center overflow-hidden [&_svg]:max-w-full"
		class:hidden={!!renderError}
		dir="ltr"
	></div>
</div>

{#if tipVisible}
	<div
		class="fixed z-50 pointer-events-none rounded-lg bg-[#00313f]/95 px-2.5 py-1.5 text-xs text-white shadow-lg"
		style="left: {tipX}px; top: {tipY}px"
	>
		{#each tipRows as [key, value]}
			<div class="flex gap-2 justify-between">
				{#if key}
					<span class="text-white/60">{key}</span>
				{/if}
				<span class="font-medium">{value}</span>
			</div>
		{/each}
	</div>
{/if}
