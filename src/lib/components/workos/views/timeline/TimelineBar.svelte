<script lang="ts">
	import { STATUS_COLOR } from '../../lib/colors';
	import { STATUS_LABEL } from '../../lib/types';
	import { actualProgress } from '../../lib/progress';
	import { formatDateShort } from '../../lib/format';
	import {
		barGeometry, applyMove, applyResize, dayToTs,
		type TimelineItem, type TimelineWindow
	} from '../../lib/timeline';
	import { openTask, editTask, initials, currentWorkstream } from '../../lib/store';
	import * as HoverCard from '$lib/components/ui/hover-card';
	import TaskHoverCard from '../TaskHoverCard.svelte';
	import { toast } from 'svelte-sonner';

	export let item: TimelineItem;
	export let win: TimelineWindow;
	export let dayWidth: number;
	export let today: number;
	export let scroller: HTMLElement | null = null;
	export let disabled = false;

	$: t = item.task;
	$: color = STATUS_COLOR[t.status];
	$: pct = actualProgress(t);
	$: daysLate = today - item.endDay;
	$: stateText =
		t.status === 'done' ? '✓ Done' : t.status === 'in_progress' && pct > 0 ? `${pct}%` : STATUS_LABEL[t.status];

	// ── Drag state ──
	type Mode = 'move' | 'start' | 'end';
	let mode: Mode | null = null;
	let x0 = 0;
	let sl0 = 0;
	let dx = 0;
	let canceled = false;

	$: delta = mode ? Math.round(dx / dayWidth) : 0;
	// Preview range under the current drag (clamped like applyResize will clamp).
	$: pStart =
		mode === 'move' ? item.startDay + delta
		: mode === 'start' ? Math.min(item.startDay + delta, item.endDay)
		: item.startDay;
	$: pEnd =
		mode === 'move' ? item.endDay + delta
		: mode === 'end' ? Math.max(item.endDay + delta, item.startDay)
		: item.endDay;
	$: geom = barGeometry({ ...item, startDay: pStart, endDay: pEnd }, win, dayWidth, today);

	function down(e: PointerEvent, m: Mode) {
		if (disabled || e.button !== 0) return;
		e.stopPropagation();
		mode = m;
		x0 = e.clientX;
		sl0 = scroller?.scrollLeft ?? 0;
		dx = 0;
		canceled = false;
		(e.currentTarget as Element).setPointerCapture(e.pointerId);
	}
	function move(e: PointerEvent) {
		if (!mode || canceled) return;
		dx = e.clientX - x0 + ((scroller?.scrollLeft ?? 0) - sl0);
		// Edge auto-pan: keep dragging usable past the viewport.
		if (scroller) {
			const r = scroller.getBoundingClientRect();
			if (e.clientX > r.right - 40) scroller.scrollLeft += 16;
			else if (e.clientX < r.left + 40) scroller.scrollLeft -= 16;
		}
	}
	async function up() {
		if (!mode) return;
		const m = mode;
		const moved = Math.abs(dx) > 4;
		const d = delta;
		mode = null;
		dx = 0;
		if (canceled) return;
		if (!moved) {
			openTask(t.id);
			return;
		}
		if (d === 0) return;
		const patch = m === 'move' ? applyMove(item, d) : applyResize(item, m, d);
		try {
			await editTask(t.id, patch);
		} catch {
			toast.error('Could not update the dates'); // editTask already rolled back
		}
	}
	function key(e: KeyboardEvent) {
		if (e.key === 'Escape' && mode) {
			canceled = true;
			mode = null;
			dx = 0;
		}
	}

	const GRIP =
		'absolute top-[3px] bottom-[3px] w-[6px] rounded-[3px] bg-white border-[1.5px] border-primary opacity-0 group-hover:opacity-100 cursor-ew-resize';
</script>

<svelte:window onkeydown={key} />

<HoverCard.Root openDelay={300} closeDelay={80}>
	<HoverCard.Trigger>
		{#snippet child({ props }: { props: Record<string, any> })}
			{#if item.kind === 'milestone'}
				<span
					{...props}
					role="button"
					tabindex="0"
					class="group absolute top-1/2 -translate-y-1/2 z-10 {disabled ? '' : 'cursor-grab touch-none'} {mode ? 'cursor-grabbing' : ''}"
					style="left: {geom.left + geom.width / 2 - 8}px;"
					title={t.title}
					aria-label={t.title}
					onpointerdown={(e) => down(e, 'move')}
					onpointermove={move}
					onpointerup={up}
					onclick={() => { if (disabled) openTask(t.id); }}
					onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') openTask(t.id); }}
				>
					<span class="block w-4 h-4 rotate-45 rounded-[3px]" style="background:{color}; box-shadow: 0 1px 4px {color}66;"></span>
					{#if !disabled}
						<span class="{GRIP} -left-2.5" onpointerdown={(e) => down(e, 'start')}></span>
					{/if}
					{#if mode}
						<span class="absolute -top-7 left-0 px-2 py-0.5 rounded-md bg-gray-900 text-white text-[10px] font-medium whitespace-nowrap z-30">
							{pStart !== pEnd ? `${formatDateShort(dayToTs(pStart))} – ` : ''}{formatDateShort(dayToTs(pEnd))}
						</span>
					{/if}
				</span>
			{:else}
				<span
					{...props}
					role="button"
					tabindex="0"
					class="group absolute top-1/2 -translate-y-1/2 h-6 rounded-md z-10 flex items-center px-2 gap-1.5 text-[10px] font-semibold text-white whitespace-nowrap select-none {disabled ? '' : 'cursor-grab touch-none'} {mode ? 'cursor-grabbing' : ''}"
					title={t.title}
					aria-label={t.title}
					style="left: {geom.left}px; width: {geom.width}px; background: {t.status === 'done' || pct <= 0 || pct >= 100
						? color
						: `linear-gradient(to right, ${color} ${pct}%, ${color}42 ${pct}%)`}; box-shadow: 0 1px 3px {color}55;"
					onpointerdown={(e) => down(e, 'move')}
					onpointermove={move}
					onpointerup={up}
					onclick={() => { if (disabled) openTask(t.id); }}
					onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') openTask(t.id); }}
				>
					{#if geom.width >= 64}<span class="flex-none overflow-hidden">{stateText}</span>{/if}
					{#if geom.width >= 48 && t.assignee_ids?.length}
						<span class="ml-auto flex-none w-[18px] h-[18px] rounded-full bg-white text-[8px] font-bold inline-flex items-center justify-center" style="color:{color}">
							{initials(t.assignee_ids[0])}
						</span>
					{/if}
					{#if !disabled}
						<span class="{GRIP} -left-[3px]" onpointerdown={(e) => down(e, 'start')}></span>
						<span class="{GRIP} -right-[3px]" onpointerdown={(e) => down(e, 'end')}></span>
					{/if}
					{#if mode}
						<span class="absolute -top-7 left-0 px-2 py-0.5 rounded-md bg-gray-900 text-white text-[10px] font-medium whitespace-nowrap z-30">
							{formatDateShort(dayToTs(pStart))} – {formatDateShort(dayToTs(pEnd))}
						</span>
					{/if}
				</span>
			{/if}
		{/snippet}
	</HoverCard.Trigger>
	<HoverCard.Content
		side="top"
		align="start"
		sideOffset={8}
		class="w-[340px] p-0 overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-xl select-none"
	>
		<TaskHoverCard task={t} workstreamName={$currentWorkstream?.name ?? ''} />
	</HoverCard.Content>
</HoverCard.Root>

{#if geom.slipWidth > 0 && !mode}
	<span
		class="absolute top-1/2 -translate-y-1/2 h-6 rounded-r-md z-[9] flex items-center justify-end pr-1 pointer-events-none"
		style="left: {geom.left + geom.width}px; width: {geom.slipWidth}px; background: repeating-linear-gradient(-45deg, rgb(220 38 38 / 0.35), rgb(220 38 38 / 0.35) 4px, rgb(239 68 68 / 0.15) 4px, rgb(239 68 68 / 0.15) 8px);"
	>
		{#if geom.slipWidth >= 40}
			<span class="rounded px-1 py-px text-[9px] font-bold bg-white/95 dark:bg-gray-950/90 text-red-600 dark:text-red-400 shadow-sm">⚠ {daysLate}d</span>
		{/if}
	</span>
{/if}
