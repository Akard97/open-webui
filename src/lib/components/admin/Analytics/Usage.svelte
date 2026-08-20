<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import dayjs from 'dayjs';
	import relativeTime from 'dayjs/plugin/relativeTime';
	dayjs.extend(relativeTime);

	import {
		getUsageOverview,
		getUsageDaily,
		getUsageEventCounts,
		getUsageUsers
	} from '$lib/apis/analytics';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import ChartLine from './ChartLine.svelte';
	import UsageUserModal from './UsageUserModal.svelte';

	const i18n = getContext('i18n');

	const USERS_PAGE_SIZE = 25;

	type ToolOverview = {
		tool: string;
		active_users: number;
		sessions: number;
		events: number;
		avg_page_ms: number;
	};
	type DailyEntry = { date: string; tools: Record<string, number>; events: number };
	type EventEntry = { event_name: string; tool: string; count: number; unique_users: number };
	type UserEntry = {
		user_id: string;
		name: string;
		last_seen: number;
		sessions: number;
		events: number;
		tools: Record<string, number>;
	};

	// Time period - persist in localStorage
	const storedPeriod =
		typeof localStorage !== 'undefined'
			? parseInt(localStorage.getItem('usageAnalyticsPeriod') ?? '')
			: NaN;
	let days = [7, 30, 90].includes(storedPeriod) ? storedPeriod : 30;

	let overview: ToolOverview[] = [];
	let dailyRaw: DailyEntry[] = [];
	let eventCounts: EventEntry[] = [];
	let users: UserEntry[] = [];
	let usersTotal = 0;

	let loading = true;

	let userSort: 'events' | 'last_seen' = 'events';
	let userPage = 1;

	let selectedUser: { user_id: string; name: string } | null = null;
	let showUserModal = false;

	const formatMs = (ms: number): string => {
		if (!ms) return '—';
		const totalSeconds = Math.round(ms / 1000);
		const m = Math.floor(totalSeconds / 60);
		const s = totalSeconds % 60;
		return `${m}m ${s}s`;
	};

	const topTool = (tools: Record<string, number>): string => {
		const entries = Object.entries(tools || {});
		if (!entries.length) return '—';
		return entries.sort((a, b) => b[1] - a[1])[0][0];
	};

	const load = async () => {
		loading = true;
		try {
			const [overviewRes, dailyRes, eventsRes, usersRes] = await Promise.all([
				getUsageOverview(localStorage.token, days),
				getUsageDaily(localStorage.token, days),
				getUsageEventCounts(localStorage.token, days),
				getUsageUsers(localStorage.token, days, userSort, userPage)
			]);

			overview = overviewRes?.tools ?? [];
			dailyRaw = dailyRes?.days ?? [];
			eventCounts = eventsRes?.events ?? [];
			users = usersRes?.users ?? [];
			usersTotal = usersRes?.total ?? 0;
		} catch (err) {
			console.error('Usage dashboard load failed:', err);
		}
		loading = false;
	};

	const loadUsers = async () => {
		try {
			const usersRes = await getUsageUsers(localStorage.token, days, userSort, userPage);
			users = usersRes?.users ?? [];
			usersTotal = usersRes?.total ?? 0;
		} catch (err) {
			console.error('Failed to load users:', err);
		}
	};

	const selectPeriod = (value: number) => {
		days = value;
		if (typeof localStorage !== 'undefined') {
			localStorage.setItem('usageAnalyticsPeriod', value.toString());
		}
		userPage = 1;
		load();
	};

	const selectUserSort = (key: 'events' | 'last_seen') => {
		if (userSort === key) return;
		userSort = key;
		userPage = 1;
		loadUsers();
	};

	const nextUserPage = () => {
		if (userPage * USERS_PAGE_SIZE < usersTotal) {
			userPage += 1;
			loadUsers();
		}
	};

	const prevUserPage = () => {
		if (userPage > 1) {
			userPage -= 1;
			loadUsers();
		}
	};

	const openUser = (u: UserEntry) => {
		selectedUser = { user_id: u.user_id, name: u.name };
		showUserModal = true;
	};

	const toolColors = [
		'#3b82f6',
		'#10b981',
		'#f59e0b',
		'#ef4444',
		'#8b5cf6',
		'#ec4899',
		'#06b6d4',
		'#84cc16'
	];

	// Zero-fill the full requested date range client-side so the chart always
	// spans `days` days (not just the days that happened to have events).
	const buildDateRange = (numDays: number): string[] => {
		const out: string[] = [];
		const today = new Date();
		const todayUtc = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
		for (let i = numDays - 1; i >= 0; i--) {
			const d = new Date(todayUtc - i * 86_400_000);
			out.push(d.toISOString().slice(0, 10));
		}
		return out;
	};

	$: toolNames = [...new Set(dailyRaw.flatMap((d) => Object.keys(d.tools || {})))];
	$: dailyByDate = new Map(dailyRaw.map((d) => [d.date, d]));
	$: dailyData = buildDateRange(days).map((date) => {
		const d = dailyByDate.get(date);
		return {
			date,
			models: Object.fromEntries(toolNames.map((t) => [t, d?.tools?.[t] ?? 0]))
		};
	});
	$: chartPeriod = (days === 7 ? 'week' : days === 90 ? 'year' : 'month') as
		| 'hour'
		| 'week'
		| 'month'
		| 'year'
		| 'all';

	onMount(load);
</script>

<!-- User activity modal -->
<UsageUserModal
	bind:show={showUserModal}
	user={selectedUser}
	{days}
	onClose={() => (selectedUser = null)}
/>

<!-- Header with title and period selector -->
<div
	class="pt-0.5 pb-1 gap-1 flex flex-row justify-between items-center sticky top-0 z-10 bg-white dark:bg-gray-900"
>
	<div class="text-lg font-medium px-0.5 shrink-0">
		{$i18n.t('Usage')}
	</div>
	<div class="flex items-center gap-2 flex-wrap justify-end min-w-0">
		<select
			value={days}
			on:change={(e) => selectPeriod(parseInt((e.target as HTMLSelectElement).value))}
			class="w-fit pr-8 rounded-sm px-2 text-xs bg-transparent outline-none text-right"
		>
			<option value={7}>{$i18n.t('Last 7 days')}</option>
			<option value={30}>{$i18n.t('Last 30 days')}</option>
			<option value={90}>{$i18n.t('Last 90 days')}</option>
		</select>
	</div>
</div>

{#if loading}
	<div class="my-10 flex justify-center">
		<Spinner className="size-5" />
	</div>
{:else}
	<!-- Overview cards -->
	<div
		class="grid gap-3 mb-4"
		style="grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));"
	>
		{#each overview as t (t.tool)}
			<div class="border border-gray-50 dark:border-gray-850 rounded-lg px-3 py-2">
				<div class="text-xs text-gray-500 dark:text-gray-400 mb-1 truncate capitalize">
					{t.tool}
				</div>
				<div class="text-xl font-medium text-gray-900 dark:text-white">
					{t.active_users.toLocaleString()}
				</div>
				<div class="text-xs text-gray-400 mb-2">{$i18n.t('Active Users')}</div>
				<div class="flex justify-between text-xs text-gray-500 dark:text-gray-400">
					<span>{t.events.toLocaleString()} {$i18n.t('events')}</span>
					<span
						>{formatMs(t.avg_page_ms)}
						<span class="text-gray-400">{$i18n.t('avg time')}</span></span
					>
				</div>
			</div>
		{/each}
		{#if overview.length === 0}
			<div class="text-gray-400 text-xs px-0.5">{$i18n.t('No data')}</div>
		{/if}
	</div>

	<!-- Daily usage chart -->
	{#if dailyData.length > 0}
		<div class="mb-4">
			<div class="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2 px-0.5">
				{$i18n.t('Daily Usage')}
			</div>
			<ChartLine
				data={dailyData}
				models={toolNames}
				colors={toolColors}
				height={200}
				period={chartPeriod}
			/>
		</div>
	{/if}

	<div class="grid md:grid-cols-2 gap-4">
		<!-- Events table -->
		<div>
			<div class="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1 px-0.5">
				{$i18n.t('Events')}
			</div>
			<div class="scrollbar-hidden relative whitespace-nowrap overflow-x-auto max-w-full">
				<table class="w-full text-sm text-left text-gray-500 dark:text-gray-400 table-auto">
					<thead class="text-xs text-gray-800 uppercase bg-transparent dark:text-gray-200">
						<tr class="border-b-[1.5px] border-gray-50 dark:border-gray-850/30">
							<th scope="col" class="px-2.5 py-2">{$i18n.t('Event')}</th>
							<th scope="col" class="px-2.5 py-2">{$i18n.t('Tool')}</th>
							<th scope="col" class="px-2.5 py-2 text-right">{$i18n.t('Count')}</th>
							<th scope="col" class="px-2.5 py-2 text-right">{$i18n.t('Users')}</th>
						</tr>
					</thead>
					<tbody>
						{#each eventCounts as e (`${e.event_name}-${e.tool}`)}
							<tr class="bg-white dark:bg-gray-900 dark:border-gray-850 text-xs">
								<td class="px-3 py-1 font-medium text-gray-900 dark:text-white">{e.event_name}</td>
								<td class="px-3 py-1 capitalize">{e.tool}</td>
								<td class="px-3 py-1 text-right">{e.count.toLocaleString()}</td>
								<td class="px-3 py-1 text-right">{e.unique_users.toLocaleString()}</td>
							</tr>
						{/each}
						{#if eventCounts.length === 0}
							<tr
								><td colspan="4" class="px-3 py-2 text-center text-gray-400"
									>{$i18n.t('No data')}</td
								></tr
							>
						{/if}
					</tbody>
				</table>
			</div>
		</div>

		<!-- Users table -->
		<div>
			<div class="flex items-center justify-between mb-1 px-0.5">
				<div class="text-xs font-medium text-gray-700 dark:text-gray-300">
					{$i18n.t('Users')}
				</div>
				<div class="flex gap-1 text-xs">
					<button
						class="px-2 py-0.5 rounded-full {userSort === 'events'
							? 'bg-gray-100 dark:bg-gray-850 text-gray-900 dark:text-white'
							: 'text-gray-400'}"
						on:click={() => selectUserSort('events')}
					>
						{$i18n.t('Most Active')}
					</button>
					<button
						class="px-2 py-0.5 rounded-full {userSort === 'last_seen'
							? 'bg-gray-100 dark:bg-gray-850 text-gray-900 dark:text-white'
							: 'text-gray-400'}"
						on:click={() => selectUserSort('last_seen')}
					>
						{$i18n.t('Recently Seen')}
					</button>
				</div>
			</div>
			<div class="scrollbar-hidden relative whitespace-nowrap overflow-x-auto max-w-full">
				<table class="w-full text-sm text-left text-gray-500 dark:text-gray-400 table-auto">
					<thead class="text-xs text-gray-800 uppercase bg-transparent dark:text-gray-200">
						<tr class="border-b-[1.5px] border-gray-50 dark:border-gray-850/30">
							<th scope="col" class="px-2.5 py-2">{$i18n.t('User')}</th>
							<th scope="col" class="px-2.5 py-2">{$i18n.t('Last Seen')}</th>
							<th scope="col" class="px-2.5 py-2 text-right">{$i18n.t('Sessions')}</th>
							<th scope="col" class="px-2.5 py-2 text-right">{$i18n.t('Events')}</th>
							<th scope="col" class="px-2.5 py-2">{$i18n.t('Top Tool')}</th>
						</tr>
					</thead>
					<tbody>
						{#each users as u (u.user_id)}
							<tr
								class="bg-white dark:bg-gray-900 dark:border-gray-850 text-xs cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
								on:click={() => openUser(u)}
							>
								<td
									class="px-3 py-1 font-medium text-gray-900 dark:text-white truncate max-w-[150px]"
								>
									{u.name}
								</td>
								<td class="px-3 py-1">{dayjs(u.last_seen).fromNow()}</td>
								<td class="px-3 py-1 text-right">{u.sessions.toLocaleString()}</td>
								<td class="px-3 py-1 text-right">{u.events.toLocaleString()}</td>
								<td class="px-3 py-1 capitalize">{topTool(u.tools)}</td>
							</tr>
						{/each}
						{#if users.length === 0}
							<tr
								><td colspan="5" class="px-3 py-2 text-center text-gray-400"
									>{$i18n.t('No data')}</td
								></tr
							>
						{/if}
					</tbody>
				</table>
			</div>
			{#if usersTotal > USERS_PAGE_SIZE}
				<div
					class="flex items-center justify-end gap-2 mt-1.5 text-xs text-gray-500 dark:text-gray-400"
				>
					<button
						class="px-2 py-0.5 rounded disabled:opacity-30 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-850"
						disabled={userPage === 1}
						on:click={prevUserPage}
					>
						{$i18n.t('Previous')}
					</button>
					<span>{userPage} / {Math.ceil(usersTotal / USERS_PAGE_SIZE)}</span>
					<button
						class="px-2 py-0.5 rounded disabled:opacity-30 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-850"
						disabled={userPage * USERS_PAGE_SIZE >= usersTotal}
						on:click={nextUserPage}
					>
						{$i18n.t('Next')}
					</button>
				</div>
			{/if}
		</div>
	</div>
{/if}
