<script lang="ts">
	import type { TimelineWidget } from '$lib/utils/widgets';

	export let widget: TimelineWidget;
</script>

<div
	class="w-full rounded-2xl border border-gray-100 dark:border-gray-850 bg-white dark:bg-gray-900 shadow-sm p-4"
>
	<div class="flex flex-col">
		{#each widget.items as item, idx}
			{@const status = item.status ?? 'pending'}
			<div class="relative flex gap-3 pb-4 last:pb-0">
				<!-- connector line -->
				{#if idx < widget.items.length - 1}
					<div
						class="absolute top-4 bottom-0 start-[7px] w-px bg-gray-200 dark:bg-gray-800"
					></div>
				{/if}

				<!-- status dot -->
				<div class="relative z-10 mt-1 shrink-0">
					{#if status === 'done'}
						<div
							class="size-[15px] rounded-full bg-gradient-to-br from-[#769a4a] to-[#5a7c37] flex items-center justify-center"
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 24 24"
								fill="none"
								stroke="white"
								stroke-width="3.5"
								class="size-2.5"
							>
								<path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5" />
							</svg>
						</div>
					{:else if status === 'active'}
						<div class="relative size-[15px]">
							<div
								class="absolute inset-0 rounded-full bg-[#00a5ba]/40 animate-ping"
							></div>
							<div
								class="relative size-[15px] rounded-full bg-gradient-to-br from-[#00a5ba] to-[#026c80] ring-2 ring-[#00a5ba]/30"
							></div>
						</div>
					{:else}
						<div
							class="size-[15px] rounded-full border-2 border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900"
						></div>
					{/if}
				</div>

				<div class="min-w-0 grow">
					<div class="flex flex-wrap items-baseline gap-x-2">
						<span
							class="font-medium leading-snug {status === 'pending'
								? 'text-gray-500 dark:text-gray-400'
								: 'text-[#00313f] dark:text-gray-50'}"
						>
							{item.title}
						</span>
						{#if item.date}
							<span class="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">
								{item.date}
							</span>
						{/if}
					</div>
					{#if item.description}
						<div class="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
							{item.description}
						</div>
					{/if}
				</div>
			</div>
		{/each}
	</div>
</div>
