<script lang="ts">
	import type { TasksWidget } from '$lib/utils/widgets';
	import { STATUS_COLOR, PRIORITY_COLOR, PRIORITY_LABEL, tint } from '$lib/components/workos/lib/colors';
	import { STATUS_LABEL } from '$lib/components/workos/lib/types';

	export let widget: TasksWidget;

	// Unknown statuses/priorities from model drift render gray, never crash.
	const FALLBACK = '#6b7280';
	const own = (map: object, key: string): string | undefined =>
		Object.hasOwn(map, key) ? (map as Record<string, string>)[key] : undefined;
	const statusColor = (s: string) => own(STATUS_COLOR, s) ?? FALLBACK;
	const statusLabel = (s: string) => own(STATUS_LABEL, s) ?? s.replace(/_/g, ' ');
	const priorityColor = (p: string) => own(PRIORITY_COLOR, p) ?? FALLBACK;
	const priorityLabel = (p: string) => own(PRIORITY_LABEL, p) ?? p;

	// A date-only due is overdue once its day has fully passed (local clock).
	const overdue = (due?: string): boolean => {
		if (!due) return false;
		const d = new Date(`${due}T23:59:59`);
		return !isNaN(d.getTime()) && d.getTime() < Date.now();
	};

	const taskUrl = (item: { id?: string; ws?: string }): string | null =>
		item.id && item.ws
			? `/workos?ws=${encodeURIComponent(item.ws)}&task=${encodeURIComponent(item.id)}`
			: null;
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

	{#if widget.layout === 'cards'}
		<div class="grid grid-cols-1 sm:grid-cols-2 gap-2 p-2">
			{#each widget.items as item}
				{@const url = taskUrl(item)}
				<svelte:element
					this={url ? 'a' : 'div'}
					href={url ?? undefined}
					target={url ? '_blank' : undefined}
					rel={url ? 'noopener' : undefined}
					class="group/task relative flex flex-col gap-1.5 rounded-xl border border-gray-100 dark:border-gray-850 p-3 {url
						? 'cursor-pointer transition hover:border-[#00a5ba]/40 hover:shadow-sm'
						: ''}"
				>
					<div class="flex items-start gap-2">
						{#if item.key}
							<span class="shrink-0 pt-0.5 font-mono text-xs text-gray-400 dark:text-gray-500">
								{item.key}
							</span>
						{/if}
						<span class="min-w-0 flex-1 text-sm font-medium text-gray-800 dark:text-gray-100">
							{item.title}
						</span>
						{#if url}
							<svg
								xmlns="http://www.w3.org/2000/svg"
								fill="none"
								viewBox="0 0 24 24"
								stroke-width="2"
								stroke="currentColor"
								class="invisible size-3.5 shrink-0 text-gray-400 group-hover/task:visible group-focus-visible/task:visible"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M13.5 6H5.25A2.25 2.25 0 0 0 3 8.25v10.5A2.25 2.25 0 0 0 5.25 21h10.5A2.25 2.25 0 0 0 18 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
								/>
							</svg>
						{/if}
					</div>
					<div class="flex flex-wrap items-center gap-x-2 gap-y-1">
						{#if item.status}
							<span
								class="inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-0.5 text-[11px] font-medium"
								style="background:{tint(statusColor(item.status))}; color:{statusColor(item.status)}"
							>
								<span class="size-1.5 rounded-full" style="background:{statusColor(item.status)}"
								></span>
								{statusLabel(item.status)}
							</span>
						{/if}
						{#if item.priority}
							<span
								class="whitespace-nowrap text-[11px] font-medium"
								style="color:{priorityColor(item.priority)}"
							>
								&#x2691; {priorityLabel(item.priority)}
							</span>
						{/if}
						{#if item.due}
							<span
								class="whitespace-nowrap text-[11px] {overdue(item.due)
									? 'font-medium text-[#c96b5d]'
									: 'text-gray-500 dark:text-gray-400'}"
							>
								{item.due}
							</span>
						{/if}
					</div>
					{#if item.progress != null}
						<div class="flex items-center gap-2">
							<div
								class="h-1 flex-1 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800"
							>
								<div
									class="h-full rounded-full bg-[#00a5ba]"
									style="width:{item.progress}%"
								></div>
							</div>
							<span class="text-[10px] text-gray-400">{item.progress}%</span>
						</div>
					{/if}
					{#if item.note}
						<div class="text-xs text-gray-500 dark:text-gray-400">{item.note}</div>
					{/if}
					{#if item.assignees?.length}
						<div class="text-[11px] text-gray-400 dark:text-gray-500">
							{item.assignees.join(', ')}
						</div>
					{/if}
				</svelte:element>
			{/each}
		</div>
	{:else}
		<div>
			{#each widget.items as item, idx}
				{@const url = taskUrl(item)}
				<svelte:element
					this={url ? 'a' : 'div'}
					href={url ?? undefined}
					target={url ? '_blank' : undefined}
					rel={url ? 'noopener' : undefined}
					class="group/task block px-4 py-2.5 {idx > 0
						? 'border-t border-gray-50 dark:border-gray-850/60'
						: ''} {url ? 'cursor-pointer transition hover:bg-gray-50/80 dark:hover:bg-gray-850/40' : ''}"
				>
					<div class="flex min-w-0 items-center gap-2">
						{#if item.key}
							<span class="shrink-0 font-mono text-xs text-gray-400 dark:text-gray-500">
								{item.key}
							</span>
						{/if}
						<span class="min-w-0 truncate text-sm font-medium text-gray-800 dark:text-gray-100">
							{item.title}
						</span>
						<span class="ms-auto flex shrink-0 items-center gap-2">
							{#if item.status}
								<span
									class="inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-0.5 text-[11px] font-medium"
									style="background:{tint(statusColor(item.status))}; color:{statusColor(
										item.status
									)}"
								>
									<span
										class="size-1.5 rounded-full"
										style="background:{statusColor(item.status)}"
									></span>
									{statusLabel(item.status)}
								</span>
							{/if}
							{#if item.priority}
								<span
									class="whitespace-nowrap text-[11px] font-medium"
									style="color:{priorityColor(item.priority)}"
								>
									&#x2691; {priorityLabel(item.priority)}
								</span>
							{/if}
							{#if item.due}
								<span
									class="whitespace-nowrap text-[11px] {overdue(item.due)
										? 'font-medium text-[#c96b5d]'
										: 'text-gray-500 dark:text-gray-400'}"
								>
									{item.due}
								</span>
							{/if}
							{#if item.progress != null}
								<span class="flex w-20 items-center gap-1.5">
									<span
										class="h-1 flex-1 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800"
									>
										<span
											class="block h-full rounded-full bg-[#00a5ba]"
											style="width:{item.progress}%"
										></span>
									</span>
									<span class="text-[10px] text-gray-400">{item.progress}%</span>
								</span>
							{/if}
							{#if url}
								<svg
									xmlns="http://www.w3.org/2000/svg"
									fill="none"
									viewBox="0 0 24 24"
									stroke-width="2"
									stroke="currentColor"
									class="invisible size-3.5 text-gray-400 group-hover/task:visible group-focus-visible/task:visible"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										d="M13.5 6H5.25A2.25 2.25 0 0 0 3 8.25v10.5A2.25 2.25 0 0 0 5.25 21h10.5A2.25 2.25 0 0 0 18 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
									/>
								</svg>
							{/if}
						</span>
					</div>
					{#if item.note || item.assignees?.length}
						<div class="mt-0.5 flex min-w-0 items-baseline gap-2 {item.key ? 'ps-0' : ''}">
							{#if item.note}
								<span class="min-w-0 flex-1 truncate text-xs text-gray-500 dark:text-gray-400">
									{item.note}
								</span>
							{/if}
							{#if item.assignees?.length}
								<span class="ms-auto shrink-0 text-[11px] text-gray-400 dark:text-gray-500">
									{item.assignees.join(', ')}
								</span>
							{/if}
						</div>
					{/if}
				</svelte:element>
			{/each}
		</div>
	{/if}
</div>
