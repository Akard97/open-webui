<script lang="ts">
	import dayjs from 'dayjs';
	import { rotateHeatmap } from '$lib/utils/usageStats';

	export let matrix: number[][] = []; // 7×24, UTC, row 0 = Sunday

	const offset = -new Date().getTimezoneOffset() / 60;
	// dayjs().day(i) = day-of-week i (0 = Sunday), locale-aware short label.
	const dayLabels = Array.from({ length: 7 }, (_, i) => dayjs().day(i).format('dd'));

	$: local = matrix.length === 7 ? rotateHeatmap(matrix, offset) : [];
	$: max = Math.max(1, ...local.flat());
</script>

{#if local.length === 7}
	<div class="flex flex-col gap-[3px]">
		{#each local as row, d}
			<div class="flex items-center gap-[3px]">
				<div class="w-8 shrink-0 text-[10px] text-gray-400 text-right pr-1">
					{dayLabels[d]}
				</div>
				{#each row as count, h}
					<div
						class="h-4 flex-1 rounded-[2px] min-w-0"
						style="background-color: rgba(59,130,246,{count === 0
							? 0.05
							: 0.2 + 0.8 * (count / max)})"
						title={`${dayLabels[d]} ${h}:00 — ${count}`}
					></div>
				{/each}
			</div>
		{/each}
		<div class="flex items-center gap-[3px]">
			<div class="w-8 shrink-0"></div>
			{#each Array.from({ length: 24 }, (_, h) => h) as h}
				<div class="flex-1 min-w-0 text-center text-[9px] text-gray-400">
					{h % 6 === 0 ? h : ''}
				</div>
			{/each}
		</div>
	</div>
{/if}
