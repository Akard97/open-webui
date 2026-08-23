<script lang="ts">
	import Modal from '$lib/components/common/Modal.svelte';
	import { getContext } from 'svelte';
	import dayjs from 'dayjs';
	import relativeTime from 'dayjs/plugin/relativeTime';
	import { getUsageUserActivity, getUsageUserSummary } from '$lib/apis/analytics';
	import { busiestHour } from '$lib/utils/usageStats';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import UsageBars from './UsageBars.svelte';
	import ChartLine from './ChartLine.svelte';

	dayjs.extend(relativeTime);

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

	// Static list matching the backend TOOLS set (models/usage.py), so the
	// filter isn't limited to whatever tools happen to appear on the loaded
	// page of activity.
	const TOOLS = ['chat', 'workos', 'policy', 'home', 'admin', 'settings', 'notes', 'other'];

	let selectedTool: string | null = null;
	let activity: ActivityEntry[] = [];
	let total = 0;
	let page = 1;
	let loading = false;
	let allLoaded = false;

	// Request-generation counter: a response is applied only if no newer
	// request has started since, so a slow stale response (old tool filter,
	// old user, closed modal) can never clobber newer state.
	let reqSeq = 0;

	type Summary = {
		first_seen: number;
		last_seen: number;
		sessions: number;
		avg_session_ms: number;
		hours: number[];
		daily: { date: string; events: number }[];
		tools: Record<string, number>;
		models: { model: string; messages: number }[];
	};

	let summary: Summary | null = null;

	const tzOffset = -new Date().getTimezoneOffset() / 60;

	const formatMs = (ms: number): string => {
		if (!ms) return '—';
		const totalSeconds = Math.round(ms / 1000);
		const m = Math.floor(totalSeconds / 60);
		const s = totalSeconds % 60;
		return `${m}m ${s}s`;
	};

	const loadSummary = async () => {
		if (!user?.user_id) return;
		const seq = reqSeq; // ride the same invalidation counter
		try {
			const res = await getUsageUserSummary(localStorage.token, user.user_id, days);
			if (seq !== reqSeq) return;
			summary = res;
		} catch (err) {
			if (seq !== reqSeq) return;
			console.error('Failed to load user summary:', err);
			summary = null;
		}
	};

	$: sparklineData = (summary?.daily ?? []).map((d) => ({
		date: d.date,
		models: { events: d.events }
	}));
	$: hour = summary ? busiestHour(summary.hours, tzOffset) : null;

	const close = () => {
		show = false;
		reqSeq++; // invalidate any in-flight request
		selectedTool = null;
		activity = [];
		total = 0;
		page = 1;
		allLoaded = false;
		loading = false;
		summary = null;
		onClose();
	};

	const load = async () => {
		if (!user?.user_id) return;
		const seq = ++reqSeq;
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
			if (seq !== reqSeq) return;
			activity = res?.events ?? [];
			total = res?.total ?? 0;
			allLoaded = activity.length === 0 || activity.length >= total;
		} catch (err) {
			if (seq !== reqSeq) return;
			console.error('Failed to load user activity:', err);
			activity = [];
			total = 0;
			allLoaded = true;
		}
		loading = false;
	};

	const loadMore = async () => {
		if (!user?.user_id || loading || allLoaded) return;
		const seq = ++reqSeq;
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
			if (seq !== reqSeq) return;
			const newEvents = res?.events ?? [];
			activity = [...activity, ...newEvents];
			total = res?.total ?? total;
			page = nextPage;
			// Latch when a page comes back empty: the server has nothing more
			// for this window even if `total` suggests otherwise (e.g. events
			// pruned between requests) — prevents an infinite Load more loop.
			allLoaded = newEvents.length === 0 || activity.length >= total;
		} catch (err) {
			if (seq !== reqSeq) return;
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
		total = 0;
		page = 1;
		allLoaded = false;
		summary = null;
		load();
		loadSummary();
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

		<div class="px-5 pb-2">
			{#if summary}
				<div class="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-3 text-xs">
					<div>
						<div class="text-gray-400">{$i18n.t('First seen')}</div>
						<div class="font-medium text-gray-900 dark:text-white">
							{summary.first_seen ? dayjs(summary.first_seen).format('MMM D, YYYY') : '—'}
						</div>
					</div>
					<div>
						<div class="text-gray-400">{$i18n.t('Last Seen')}</div>
						<div class="font-medium text-gray-900 dark:text-white">
							{summary.last_seen ? dayjs(summary.last_seen).fromNow() : '—'}
						</div>
					</div>
					<div>
						<div class="text-gray-400">{$i18n.t('Sessions')}</div>
						<div class="font-medium text-gray-900 dark:text-white">
							{summary.sessions.toLocaleString()}
						</div>
					</div>
					<div>
						<div class="text-gray-400">{$i18n.t('Avg session')}</div>
						<div class="font-medium text-gray-900 dark:text-white">
							{formatMs(summary.avg_session_ms)}
						</div>
					</div>
					<div>
						<div class="text-gray-400">{$i18n.t('Busiest hour')}</div>
						<div class="font-medium text-gray-900 dark:text-white">
							{hour !== null ? `${hour}:00` : '—'}
						</div>
					</div>
				</div>

				{#if sparklineData.length > 1}
					<div class="mb-3">
						<ChartLine
							data={sparklineData}
							models={['events']}
							colors={['#3b82f6']}
							height={80}
							period={days === 7 ? 'week' : days === 90 ? 'year' : 'month'}
						/>
					</div>
				{/if}

				<div class="grid sm:grid-cols-2 gap-4 mb-1">
					{#if Object.keys(summary.tools).length > 0}
						<div>
							<div class="text-xs text-gray-400 mb-1">{$i18n.t('Tools')}</div>
							<UsageBars
								items={Object.entries(summary.tools)
									.sort((a, b) => b[1] - a[1])
									.map(([label, value]) => ({ label, value }))}
							/>
						</div>
					{/if}
					{#if summary.models.length > 0}
						<div>
							<div class="text-xs text-gray-400 mb-1">{$i18n.t('Top Models')}</div>
							<UsageBars
								items={summary.models.map((m) => ({ label: m.model, value: m.messages }))}
							/>
						</div>
					{/if}
				</div>
			{/if}
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
					{#each TOOLS as t}
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
