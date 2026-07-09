<script lang="ts">
	import { PALETTE, badgeColorForValue, type TableWidget } from '$lib/utils/widgets';

	export let widget: TableWidget;

	const alignClass = (align?: string) =>
		align === 'right' ? 'text-end' : align === 'center' ? 'text-center' : 'text-start';

	const cellText = (value: string | number | boolean | null | undefined): string =>
		value == null ? '' : String(value);
</script>

<div
	class="not-prose w-full overflow-hidden rounded-2xl border border-gray-100 dark:border-gray-850 bg-white dark:bg-gray-900 shadow-sm"
>
	{#if widget.title}
		<div
			class="px-4 pt-3 pb-2 text-sm font-semibold text-[#00313f] dark:text-gray-50 border-b border-gray-100 dark:border-gray-850"
		>
			{widget.title}
		</div>
	{/if}

	<div class="overflow-x-auto scrollbar-hidden">
		<table class="w-full text-sm" dir="auto">
			<thead>
				<tr class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
					{#each widget.columns as column}
						<th class="px-4 py-2.5 font-medium {alignClass(column.align)}">
							{column.label}
						</th>
					{/each}
				</tr>
			</thead>
			<tbody>
				{#each widget.rows as row, rowIdx}
					<tr
						class="border-t border-gray-50 dark:border-gray-850/60 {rowIdx % 2 === 1
							? 'bg-gray-50/60 dark:bg-gray-850/30'
							: ''}"
					>
						{#each widget.columns as column}
							{@const text = cellText(row[column.key])}
							<td class="px-4 py-2 text-gray-700 dark:text-gray-200 {alignClass(column.align)}">
								{#if column.badge && text !== ''}
									<span
										class="inline-flex rounded-full px-2 py-0.5 text-xs font-medium {PALETTE[
											badgeColorForValue(text)
										].badge}"
									>
										{text}
									</span>
								{:else}
									{text}
								{/if}
							</td>
						{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>
