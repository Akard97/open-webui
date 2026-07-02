<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { user } from '$lib/stores';
	import Icon from '../ui/Icon.svelte';
	// Bundle the logo as a hashed build asset instead of loading it from the
	// backend's /static dir, which gets wiped when the backend image is rebuilt.
	import workosLogoDark from '../assets/workos-logo-dark.png';
	import workosLogoLight from '../assets/workos-logo-light.png';
	import StatusDot from '../ui/StatusDot.svelte';
	import Avatar from './commandcenter/Avatar.svelte';
	import TaskHoverCard from './TaskHoverCard.svelte';
	import * as HoverCard from '$lib/components/ui/hover-card';
	import type { Task, TaskStatus, MyWorkSegment } from '../lib/types';
	import { STATUS_LABEL } from '../lib/types';
	import { STATUS_COLOR, PRIORITY_COLOR } from '../lib/colors';
	import { taskHealth, HEALTH_LABEL, type TaskHealth } from '../lib/progress';
	import { bucketByDueDate } from '../lib/buckets';
	import { computeStats } from '../lib/stats';
	import { summarizeNotification } from '../lib/notifications';
	import {
		myTasks, workstreams, notifications,
		loadMyWork, teardownMyWork, loadNotifications, openTask, openNotification
	} from '../lib/store';

	const now = Date.now();
	const startToday = new Date(now).setHours(0, 0, 0, 0);
	const endToday = startToday + 86_399_999;

	const STATUS_SHAPE: Record<TaskStatus, 'dashed' | 'ring' | 'half' | 'check' | 'x'> = {
		backlog: 'dashed', todo: 'ring', in_progress: 'half', in_review: 'half', done: 'check', canceled: 'x'
	};

	// Health → chip tint, mirrored from the board's TaskCard so My Work reads the
	// same on-track / at-risk / behind / overdue scale.
	const HEALTH_CHIP: Record<TaskHealth, string> = {
		on_track: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
		at_risk: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
		behind: 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
		overdue: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
	};

	const fmtDue = (ms: number) => new Date(ms).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
	const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
	function ago(ms: number): string {
		const s = Math.max(0, Math.floor((now - ms) / 1000));
		if (s < 60) return `${s}s`;
		const m = Math.floor(s / 60); if (m < 60) return `${m}m`;
		const h = Math.floor(m / 60); if (h < 24) return `${h}h`;
		return `${Math.floor(h / 24)}d`;
	}
	function dayLabel(ms: number): { day: string; date: string } {
		const d = new Date(ms);
		const diff = Math.round((new Date(d).setHours(0, 0, 0, 0) - startToday) / 86_400_000);
		const day = diff === 0 ? 'Today' : diff === 1 ? 'Tomorrow' : d.toLocaleDateString(undefined, { weekday: 'long' });
		const date = d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }).replace(', ', ' · ');
		return { day, date };
	}
	const greetWord = () => { const h = new Date(now).getHours(); return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'; };

	onMount(() => { void loadMyWork(); void loadNotifications(); });
	onDestroy(() => teardownMyWork());

	$: uid = $user?.id ?? '';
	$: firstName = ($user?.name ?? 'there').split(' ')[0];
	$: dateLine = `${new Date(now).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })} · ${buckets.today.length} task${buckets.today.length === 1 ? '' : 's'} due today across your Workstreams.`;

	$: openTasks = $myTasks.filter((t) => t.status !== 'done' && t.status !== 'canceled');
	$: buckets = bucketByDueDate(openTasks, now);
	$: openStats = computeStats(openTasks, now);
	$: doneThisWeek = computeStats($myTasks, now).doneThisWeek;

	// Done in the prior 7-day window → delta arrow + "vs N last week".
	const WEEK = 7 * 86_400_000;
	$: doneLastWeek = $myTasks.filter(
		(t) => t.status === 'done' && (t.completed_at ?? 0) >= now - 2 * WEEK && (t.completed_at ?? 0) < now - WEEK
	).length;

	// Oldest task still waiting on review → "oldest 2d ago".
	$: reviewTasks = openTasks.filter((t) => t.status === 'in_review');
	$: oldestReview = reviewTasks.length ? Math.min(...reviewTasks.map((t) => t.updated_at)) : null;

	$: stats4 = [
		{ value: $myTasks.filter((t) => (t.assignee_ids ?? []).includes(uid)).length, label: 'Assigned to you',
			icon: 'list', iconColor: 'text-gray-700 dark:text-gray-200', sub: `${buckets.today.length} due today`, delta: null as number | null },
		{ value: buckets.today.length + buckets.thisWeek.length, label: 'Due this week',
			icon: 'clock', iconColor: 'text-gray-400 dark:text-gray-500', sub: `${openStats.inProgress} in progress`, delta: null as number | null },
		{ value: reviewTasks.length, label: 'Waiting on review',
			icon: 'eye', iconColor: 'text-gray-400 dark:text-gray-500',
			sub: oldestReview ? `oldest ${ago(oldestReview)} ago` : 'all clear', delta: null as number | null },
		{ value: doneThisWeek, label: 'Done this week',
			icon: 'circle-check', iconColor: 'text-emerald-500 dark:text-emerald-400',
			sub: `vs ${doneLastWeek} last week`, delta: doneThisWeek - doneLastWeek }
	];

	$: overdue = buckets.overdue;

	// Workstream filter chips (derived from the user's open tasks).
	$: wsList = (() => {
		const ids = [...new Set(openTasks.map((t) => t.workstream_id))];
		return ids
			.map((id) => { const w = $workstreams.find((x) => x.id === id); return w ? { id, name: w.name } : null; })
			.filter((x): x is { id: string; name: string } => x !== null);
	})();
	$: wsChips = [{ id: 'all', name: 'All Workstreams' }, ...wsList];
	let wsFilter = 'all';

	// Ownership segment toggle — scopes the My-tasks list to all / assigned-to-me /
	// created-by-me (the dashboard stats above stay across all your work).
	let segment: MyWorkSegment = 'all';
	const SEGMENTS: { k: MyWorkSegment; label: string }[] = [
		{ k: 'all', label: 'All' },
		{ k: 'assigned', label: 'Assigned to me' },
		{ k: 'created', label: 'Created by me' }
	];

	// "Need attention" toggle (title row) — scopes the My-tasks list to tasks that are
	// overdue or about to be (due within ATTENTION_WINDOW of now). Auto-clears when
	// nothing qualifies so the (then-hidden) toggle can't strand the list empty.
	const ATTENTION_WINDOW = 2 * 86_400_000; // "about to be overdue" = due within 2 days
	const needsAttn = (t: Task) => t.due_date != null && t.due_date <= endToday + ATTENTION_WINDOW;
	$: attentionCount = openTasks.filter(needsAttn).length;
	let attentionOnly = false;
	$: if (!attentionCount && attentionOnly) attentionOnly = false;

	$: filtered = openTasks
		.filter((t) => wsFilter === 'all' || t.workstream_id === wsFilter)
		.filter((t) =>
			segment === 'assigned' ? (t.assignee_ids ?? []).includes(uid)
			: segment === 'created' ? t.created_by_id === uid
			: true)
		.filter((t) => !attentionOnly || needsAttn(t))
		.slice()
		.sort((a, b) => (a.due_date ?? 8_640_000_000_000) - (b.due_date ?? 8_640_000_000_000));

	// Workload by priority.
	$: workTotal = openTasks.length;
	$: segments = (['urgent', 'high', 'medium', 'low'] as const)
		.map((p) => ({ label: cap(p), n: openStats.byPriority[p], color: PRIORITY_COLOR[p] }))
		.filter((s) => s.n > 0)
		.map((s) => ({ ...s, w: workTotal ? Math.round((s.n / workTotal) * 1000) / 10 : 0 }));

	// Upcoming agenda.
	$: upcoming = openTasks
		.filter((t) => t.due_date != null && t.due_date >= startToday)
		.slice()
		.sort((a, b) => (a.due_date as number) - (b.due_date as number))
		.slice(0, 5)
		.map((t) => ({ task: t, ...dayLabel(t.due_date as number) }));

	// Activity + mentions from notifications.
	function toAct(n: any) {
		const who = n.data?.actor_name ?? 'Someone';
		const target = n.data?.task_key ?? '';
		let action = 'updated', detail = '';
		if (n.type === 'assigned') { action = 'assigned'; detail = 'to you'; }
		else if (n.type === 'mentioned') action = 'mentioned you in';
		else if (n.type === 'commented') action = 'commented on';
		return { who, first: who.split(' ')[0], action, target, detail, when: ago(n.created_at), n };
	}
	$: activity = $notifications.slice(0, 5).map(toAct);
	$: mentions = $notifications.filter((n) => n.type === 'mentioned').slice(0, 3);
	$: unreadMentions = $notifications.filter((n) => n.type === 'mentioned' && !n.read).length;

	const wsName = (t: Task) => $workstreams.find((w) => w.id === t.workstream_id)?.name ?? '';
	function dueClass(t: Task): string {
		if (t.due_date == null) return 'text-gray-400';
		if (t.due_date < startToday) return 'text-red-500';
		if (t.due_date <= endToday) return 'text-primary';
		return 'text-gray-400';
	}

// Board-card chrome: flat white surface, hairline border, rounded-lg (8px) — no
	// resting shadow (the board cards are flat; only TaskCard lifts on hover). Dark
	// surface stays gray-900 so cards still read against the gray-950 page.
	const CARD = 'border border-gray-200 dark:border-gray-800 rounded-lg bg-white dark:bg-gray-900';

	// Shared column track for the My-tasks table — header and rows reference the same
	// string so the columns line up: Status · Task · Priority · Workstream · Due · Health.
	const GRID = 'grid-template-columns:104px minmax(0,1fr) 92px 116px 60px 80px';
</script>

<div class="h-full overflow-auto bg-white dark:bg-gray-950">
	<div class="max-w-[1240px] mx-auto px-4 md:px-9 pt-5 md:pt-7 pb-14">

		<!-- Brand -->
		<img src={workosLogoDark} class="h-10 w-auto object-contain mb-4 block dark:hidden" alt="WorkOS" />
		<img src={workosLogoLight} class="h-10 w-auto object-contain mb-4 hidden dark:block" alt="WorkOS" />

		<!-- Header -->
		<div class="flex items-center gap-4 mb-6">
			<div class="flex-1 min-w-0">
				<h1 class="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">{greetWord()}, {firstName}</h1>
				<p class="mt-1 text-sm text-gray-400 dark:text-gray-500">{dateLine}</p>
			</div>
		</div>

		<!-- Stat tiles -->
		<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-[18px]">
			{#each stats4 as s (s.label)}
				<div class="px-5 py-[13px] {CARD}">
					<span class="block {s.iconColor}"><Icon name={s.icon} size={20} /></span>
					<div class="mt-3 flex items-baseline gap-1.5">
						<span class="text-[34px] font-bold tracking-tight leading-none tabular-nums text-gray-900 dark:text-gray-100">{s.value}</span>
						{#if s.delta != null && s.delta > 0}
							<span class="inline-flex items-center gap-px text-[13px] font-semibold text-emerald-600 dark:text-emerald-400">
								<Icon name="arrow-up" size={12} />{s.delta}
							</span>
						{/if}
					</div>
					<div class="mt-2.5 text-[13px] font-semibold text-gray-700 dark:text-gray-200">{s.label}</div>
					<div class="mt-1 text-[12px] font-mono text-gray-400 dark:text-gray-500">{s.sub}</div>
				</div>
			{/each}
		</div>

		<!-- Overdue callout -->
		{#if overdue.length}
			<div class="flex items-center gap-3.5 px-4 py-3.5 border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/40 rounded-lg mb-[18px]">
				<span class="w-8 h-8 rounded-full bg-red-500 text-white flex items-center justify-center flex-none"><Icon name="alert-triangle" size={17} /></span>
				<div class="flex-1 min-w-0">
					<div class="text-sm font-semibold text-red-700 dark:text-red-300">{overdue.length} task{overdue.length === 1 ? ' is' : 's are'} overdue</div>
					<div class="text-xs text-red-700/80 dark:text-red-300/80 mt-px truncate">{overdue.map((t) => t.title).join(' · ')}</div>
				</div>
			</div>
		{/if}

		<!-- Bento grid -->
		<div class="grid grid-cols-1 lg:grid-cols-[1.55fr_1fr] gap-[18px] items-start">

			<!-- LEFT: filtered task list -->
			<div class="{CARD} overflow-hidden">
				<div class="px-[18px] pt-4 pb-3.5 border-b border-gray-100 dark:border-gray-800">
					<div class="flex items-center gap-3 mb-3">
						<span class="text-[17px] font-semibold tracking-tight text-gray-900 dark:text-gray-100">My tasks</span>
						<span class="text-xs text-gray-400 tabular-nums">{filtered.length} shown</span>
						<div class="flex-1"></div>
						{#if attentionCount}
							<button
								type="button"
								role="switch"
								onclick={() => (attentionOnly = !attentionOnly)}
								aria-checked={attentionOnly}
								class="inline-flex items-center gap-2 h-7 pl-2.5 pr-1.5 rounded-lg text-[12px] font-medium border transition-colors
									{attentionOnly
										? 'border-amber-300 bg-amber-100 text-amber-700 dark:border-amber-800 dark:bg-amber-900/40 dark:text-amber-300'
										: 'border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'}"
							>
								<Icon name="alert-triangle" size={13} />
								Need attention
								<span class="tabular-nums {attentionOnly ? '' : 'text-amber-600 dark:text-amber-400'}">{attentionCount}</span>
								<span
									class="relative inline-block w-7 h-4 rounded-full transition-colors
										{attentionOnly ? 'bg-amber-500' : 'bg-gray-300 dark:bg-gray-600'}"
								>
									<span
										class="absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white shadow transition-transform
											{attentionOnly ? 'translate-x-3' : ''}"
									></span>
								</span>
							</button>
						{/if}
						<div class="inline-flex rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-0.5">
							{#each SEGMENTS as s (s.k)}
								<button
									type="button"
									onclick={() => (segment = s.k)}
									class="h-7 px-2.5 rounded-md text-[12px] font-medium transition-colors
										{segment === s.k
											? 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 shadow-sm'
											: 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'}"
								>{s.label}</button>
							{/each}
						</div>
					</div>
					<div class="flex gap-2 flex-wrap">
						{#each wsChips as c (c.id)}
							<button
								type="button"
								onclick={() => (wsFilter = c.id)}
								class="h-7 px-3 rounded-full text-[13px] font-medium border transition-colors
									{wsFilter === c.id
										? 'border-gray-300 bg-gray-100 text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100'
										: 'border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'}"
							>{c.name}</button>
						{/each}
					</div>
				</div>
				<div class="px-2 pt-1 pb-2 overflow-x-auto">
					{#if !filtered.length}
						<div class="py-14 text-center text-sm text-gray-400">Nothing on your plate here.</div>
					{:else}
						<!-- Column header -->
						<div class="grid items-center gap-3 px-2 pb-2 text-[11px] font-medium text-gray-400 dark:text-gray-500" style={GRID}>
							<span>Status</span>
							<span>Task</span>
							<span>Priority</span>
							<span>Workstream</span>
							<span class="text-right">Due</span>
							<span class="text-right">Health</span>
						</div>
						{#each filtered as t (t.id)}
							{@const health = taskHealth(t, now)}
							<HoverCard.Root openDelay={220} closeDelay={120}>
								<HoverCard.Trigger>
									{#snippet child({ props }: { props: Record<string, any> })}
										<button
											{...props}
											type="button"
											onclick={() => openTask(t.id)}
											class="group grid items-center gap-3 w-full text-left px-2 py-2 rounded-lg border-t border-gray-100 dark:border-gray-800/60 first:border-t-0 hover:bg-gray-50 dark:hover:bg-gray-800/60 transition-colors"
											style={GRID}
										>
											<span
												class="inline-flex items-center gap-1 w-fit px-2 py-0.5 rounded-md text-[11px] font-semibold"
												style="background:{STATUS_COLOR[t.status]}24; color:{STATUS_COLOR[t.status]}"
											>
												<StatusDot shape={STATUS_SHAPE[t.status]} color={STATUS_COLOR[t.status]} size={11} />
												{STATUS_LABEL[t.status]}
											</span>
											<span class="min-w-0 text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{t.title}</span>
											{#if t.priority}
												<span class="inline-flex items-center gap-1.5 text-[13px] text-gray-600 dark:text-gray-300">
													<span class="flex-none" style="color:{PRIORITY_COLOR[t.priority]}"><Icon name="flag" size={14} /></span>{cap(t.priority)}
												</span>
											{:else}
												<span class="text-gray-300 dark:text-gray-600">—</span>
											{/if}
											<span class="inline-flex items-center gap-1.5 min-w-0 text-[13px] text-gray-500 dark:text-gray-400">
												<span class="w-1.5 h-1.5 rounded-full bg-brand-500 flex-none"></span><span class="truncate">{wsName(t)}</span>
											</span>
											<span class="text-[13px] tabular-nums text-right {dueClass(t)}">{t.due_date ? fmtDue(t.due_date) : '—'}</span>
											{#if health}
												<span class="w-fit justify-self-end rounded-md px-2 py-0.5 text-[11px] font-medium {HEALTH_CHIP[health]}">{HEALTH_LABEL[health]}</span>
											{:else}
												<span></span>
											{/if}
										</button>
									{/snippet}
								</HoverCard.Trigger>
								<HoverCard.Content
									side="right"
									align="start"
									sideOffset={10}
									class="w-[340px] p-0 overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-xl select-none"
								>
									<TaskHoverCard task={t} workstreamName={wsName(t)} {now} />
								</HoverCard.Content>
							</HoverCard.Root>
						{/each}
					{/if}
				</div>
			</div>

			<!-- RIGHT rail -->
			<div class="flex flex-col gap-[18px]">

				<!-- Workload -->
				<div class="px-[18px] py-4 {CARD}">
					<div class="flex items-baseline gap-2 mb-3.5">
						<span class="text-[15px] font-semibold text-gray-900 dark:text-gray-100">Workload</span>
						<span class="text-xs text-gray-400">by priority · {workTotal} open</span>
					</div>
					{#if segments.length}
						<div class="flex h-[11px] rounded-full overflow-hidden bg-gray-100 dark:bg-gray-800 mb-[15px]">
							{#each segments as seg (seg.label)}<div style="width:{seg.w}%; background:{seg.color}"></div>{/each}
						</div>
						<div class="grid grid-cols-2 gap-x-[18px] gap-y-[9px]">
							{#each segments as seg (seg.label)}
								<div class="flex items-center gap-2">
									<span class="w-[9px] h-[9px] rounded-[3px] flex-none" style="background:{seg.color}"></span>
									<span class="flex-1 text-[13px] text-gray-600 dark:text-gray-300">{seg.label}</span>
									<span class="text-[13px] font-medium tabular-nums text-gray-900 dark:text-gray-100">{seg.n}</span>
								</div>
							{/each}
						</div>
					{:else}
						<div class="text-xs text-gray-400">No open tasks.</div>
					{/if}
				</div>

				<!-- Upcoming -->
				<div class="px-[18px] py-4 {CARD}">
					<div class="text-[15px] font-semibold text-gray-900 dark:text-gray-100 mb-[11px]">Upcoming</div>
					{#if !upcoming.length}
						<div class="text-xs text-gray-400 py-1">Nothing scheduled.</div>
					{:else}
						{#each upcoming as d (d.task.id)}
							<button type="button" onclick={() => openTask(d.task.id)} class="w-full text-left flex gap-3 py-2 items-center">
								<div class="w-[78px] flex-none">
									<div class="text-[13px] font-medium text-gray-900 dark:text-gray-100">{d.day}</div>
									<div class="text-[11px] text-gray-400 tabular-nums">{d.date}</div>
								</div>
								<div class="w-px self-stretch bg-gray-100 dark:bg-gray-800"></div>
								<div class="flex-1 min-w-0 flex items-center gap-2">
									<span class="flex-none" style="color:{d.task.priority ? PRIORITY_COLOR[d.task.priority] : '#cbd5e1'}"><Icon name="flag" size={14} /></span>
									<span class="text-[13px] text-gray-600 dark:text-gray-300 truncate">{d.task.title}</span>
								</div>
							</button>
						{/each}
					{/if}
				</div>

				<!-- Activity -->
				<div class="px-[18px] py-4 {CARD}">
					<div class="text-[15px] font-semibold text-gray-900 dark:text-gray-100 mb-2.5">Activity</div>
					{#if !activity.length}
						<div class="text-xs text-gray-400 py-1">No recent activity.</div>
					{:else}
						{#each activity as a (a.n.id)}
							<button type="button" onclick={() => openNotification(a.n)} class="w-full text-left flex items-start gap-2.5 py-1.5">
								<Avatar name={a.who} size={22} />
								<div class="flex-1 min-w-0 text-[13px] text-gray-600 dark:text-gray-300 leading-snug">
									<b class="font-medium text-gray-900 dark:text-gray-100">{a.first}</b> {a.action}{#if a.target} <span class="text-xs font-medium text-primary tabular-nums">{a.target}</span>{/if}{#if a.detail} {a.detail}{/if}
								</div>
								<span class="text-[11px] text-gray-400 flex-none">{a.when}</span>
							</button>
						{/each}
					{/if}
				</div>

				<!-- Mentions -->
				<div class="px-[18px] py-4 {CARD}">
					<div class="flex items-center gap-2 mb-2.5">
						<span class="flex-1 text-[15px] font-semibold text-gray-900 dark:text-gray-100">Mentions</span>
						{#if unreadMentions}<span class="text-[11px] tabular-nums text-white bg-red-500 rounded-full px-1.5 py-0.5">{unreadMentions}</span>{/if}
					</div>
					{#if !mentions.length}
						<div class="text-xs text-gray-400 py-1">No mentions.</div>
					{:else}
						{#each mentions as m (m.id)}
							<button type="button" onclick={() => openNotification(m)} class="w-full text-left flex items-start gap-2.5 py-[7px]">
								<Avatar name={m.data?.actor_name ?? '?'} size={22} />
								<div class="flex-1 min-w-0">
									<div class="text-[13px] text-gray-600 dark:text-gray-300 leading-snug">{m.data?.snippet ?? summarizeNotification(m)}</div>
									<div class="text-[11px] text-gray-400 tabular-nums mt-0.5">{m.data?.task_key ?? ''} · {ago(m.created_at)}</div>
								</div>
							</button>
						{/each}
					{/if}
				</div>

			</div>
		</div>
	</div>
</div>
