<script lang="ts">
	import {
		monthSpans, dayNumber, weekdayShort, isWeekend, isWeekStart,
		type TimelineWindow, type ZoomKey
	} from '../../lib/timeline';

	export let win: TimelineWindow;
	export let dayWidth: number;
	export let zoom: ZoomKey;
	export let today: number;
	export let railW: number;

	$: spans = monthSpans(win);
	$: days = Array.from({ length: win.days }, (_, i) => win.startDay + i);
</script>

<!-- Sticky under the toolbar while the rows scroll vertically. z-30 keeps it
     above the rows' sticky rail cells (z-20), which are later in the DOM. -->
<div class="sticky top-0 z-30 flex bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800" style="width: {railW + win.days * dayWidth}px;">
	<!-- Corner cell: sticky on the horizontal axis too -->
	<div class="sticky left-0 z-10 flex-none flex items-end px-3 pb-1.5 bg-gray-50 dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 text-[10px] font-semibold tracking-wider text-gray-400 uppercase" style="width: {railW}px;">
		Task
	</div>
	<div class="flex-none">
		<!-- Month band -->
		<div class="flex h-5">
			{#each spans as s (s.startDay)}
				<div class="flex-none px-2 text-[10px] font-bold tracking-wide text-gray-500 dark:text-gray-400 uppercase overflow-hidden whitespace-nowrap border-r border-gray-200/60 dark:border-gray-800/60" style="width: {s.days * dayWidth}px;">
					{s.label}
				</div>
			{/each}
		</div>
		<!-- Day row -->
		<div class="flex h-6">
			{#each days as d (d)}
				{@const showLabel = zoom === 'quarter' ? isWeekStart(d) : true}
				<div
					class="flex-none flex items-center justify-center text-[10px] font-semibold {isWeekend(d) ? 'text-gray-300 dark:text-gray-600' : 'text-gray-500 dark:text-gray-400'}"
					style="width: {dayWidth}px;"
				>
					{#if d === today}
						<span class="inline-flex items-center justify-center min-w-[18px] h-[16px] px-1 rounded-full bg-primary text-primary-foreground">{dayNumber(d)}</span>
					{:else if showLabel}
						<span class="truncate">{zoom === 'week' ? `${weekdayShort(d)} ${dayNumber(d)}` : dayNumber(d)}</span>
					{/if}
				</div>
			{/each}
		</div>
	</div>
</div>
