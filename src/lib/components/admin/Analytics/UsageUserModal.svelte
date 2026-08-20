<script lang="ts">
	import Modal from '$lib/components/common/Modal.svelte';
	import { getContext } from 'svelte';
	import dayjs from 'dayjs';
	import { getUsageUserActivity } from '$lib/apis/analytics';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	export let show = false;
	export let user: { user_id: string; name: string } | null = null;
	export let days: number = 30;
	export let onClose: () => void = () => {};

	const i18n = getContext('i18n');

	type ActivityEntry = {
		event_name: string;
		tool: string;
		properties: Record<string, unknown>;
		source: string;
		created_at: number;
	};

	let selectedTool: string | null = null;
	let activity: ActivityEntry[] = [];
	let knownTools: string[] = [];
	let total = 0;
	let page = 1;
	let loading = false;
	let allLoaded = false;

	const mergeKnownTools = (events: ActivityEntry[]) => {
		const set = new Set(knownTools);
		events.forEach((e) => set.add(e.tool));
		knownTools = [...set];
	};

	const close = () => {
		show = false;
		selectedTool = null;
		activity = [];
		knownTools = [];
		total = 0;
		page = 1;
		allLoaded = false;
		onClose();
	};

	const load = async () => {
		if (!user?.user_id) return;
		loading = true;
		page = 1;
		try {
			const res = await getUsageUserActivity(
				localStorage.token,
				user.user_id,
				days,
				page,
				selectedTool
			);
			activity = res?.events ?? [];
			total = res?.total ?? 0;
			allLoaded = activity.length >= total;
			mergeKnownTools(activity);
		} catch (err) {
			console.error('Failed to load user activity:', err);
			activity = [];
			total = 0;
			allLoaded = true;
		}
		loading = false;
	};

	const loadMore = async () => {
		if (!user?.user_id || loading || allLoaded) return;
		loading = true;
		try {
			const nextPage = page + 1;
			const res = await getUsageUserActivity(
				localStorage.token,
				user.user_id,
				days,
				nextPage,
				selectedTool
			);
			const newEvents = res?.events ?? [];
			activity = [...activity, ...newEvents];
			total = res?.total ?? total;
			page = nextPage;
			allLoaded = activity.length >= total;
			mergeKnownTools(newEvents);
		} catch (err) {
			console.error('Failed to load more activity:', err);
		}
		loading = false;
	};

	const selectTool = (t: string | null) => {
		selectedTool = t;
		load();
	};

	// Reset and load activity whenever the modal opens for a user
	$: if (show && user?.user_id) {
		selectedTool = null;
		activity = [];
		knownTools = [];
		total = 0;
		page = 1;
		allLoaded = false;
		load();
	}
</script>

<Modal size="md" bind:show>
	{#if user}
		<div class="flex justify-between dark:text-gray-300 px-5 pt-4 pb-2">
			<div class="text-lg font-medium self-center line-clamp-1">
				{user.name}
			</div>
			<button class="self-center" on:click={close} aria-label="Close">
				<XMark className={'size-5'} />
			</button>
		</div>

		<div class="px-5 pb-4 dark:text-gray-200">
			<div class="flex items-center justify-between mb-3">
				<div class="text-xs text-gray-500 font-medium uppercase tracking-wide">
					{$i18n.t('Activity')}
				</div>
				<select
					value={selectedTool ?? ''}
					on:change={(e) => selectTool((e.target as HTMLSelectElement).value || null)}
					class="w-fit pr-8 rounded-sm px-2 text-xs bg-transparent outline-none text-right"
				>
					<option value="">{$i18n.t('All Tools')}</option>
					{#each knownTools as t}
						<option value={t}>{t}</option>
					{/each}
				</select>
			</div>

			<div
				class="scrollbar-hidden relative whitespace-nowrap overflow-x-auto overflow-y-auto max-w-full max-h-96"
			>
				<table class="w-full text-sm text-left text-gray-500 dark:text-gray-400 table-auto">
					<thead
						class="text-xs text-gray-800 uppercase bg-white dark:bg-gray-900 dark:text-gray-200 sticky top-0"
					>
						<tr class="border-b-[1.5px] border-gray-50 dark:border-gray-850/30">
							<th scope="col" class="px-2.5 py-2">{$i18n.t('Time')}</th>
							<th scope="col" class="px-2.5 py-2">{$i18n.t('Event')}</th>
							<th scope="col" class="px-2.5 py-2">{$i18n.t('Tool')}</th>
							<th scope="col" class="px-2.5 py-2">{$i18n.t('Source')}</th>
						</tr>
					</thead>
					<tbody>
						{#each activity as a, idx (`${a.created_at}-${idx}`)}
							<tr class="bg-white dark:bg-gray-900 dark:border-gray-850 text-xs">
								<td class="px-3 py-1 text-gray-400">
									{dayjs(a.created_at).format('MMM D, YYYY h:mm A')}
								</td>
								<td class="px-3 py-1 font-medium text-gray-900 dark:text-white">{a.event_name}</td>
								<td class="px-3 py-1 capitalize">{a.tool}</td>
								<td class="px-3 py-1">
									<span
										class="px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-850 text-[10px] uppercase tracking-wide"
									>
										{a.source}
									</span>
								</td>
							</tr>
						{/each}
						{#if !loading && activity.length === 0}
							<tr
								><td colspan="4" class="px-3 py-2 text-center text-gray-400"
									>{$i18n.t('No data')}</td
								></tr
							>
						{/if}
					</tbody>
				</table>
			</div>

			{#if loading && activity.length === 0}
				<div class="my-6 flex justify-center">
					<Spinner className="size-5" />
				</div>
			{/if}

			{#if !allLoaded && activity.length > 0}
				<div class="flex justify-center pt-3">
					<button
						class="px-3 py-1 text-xs font-medium bg-gray-50 hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800 rounded-full transition disabled:opacity-50"
						type="button"
						disabled={loading}
						on:click={loadMore}
					>
						{loading ? $i18n.t('Loading...') : $i18n.t('Load more')}
					</button>
				</div>
			{/if}

			<div class="flex justify-end pt-4">
				<button
					class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
					type="button"
					on:click={close}
				>
					{$i18n.t('Close')}
				</button>
			</div>
		</div>
	{/if}
</Modal>
