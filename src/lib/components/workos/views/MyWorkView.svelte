<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { user, theme as appTheme } from '$lib/stores';
	import Icon from '../ui/Icon.svelte';
	import StatusDot from '../ui/StatusDot.svelte';
	import Pills from '../ui/Pills.svelte';
	import PriorityIcon from './commandcenter/PriorityIcon.svelte';
	import Avatar from './commandcenter/Avatar.svelte';
	import type { Task, TaskStatus, Label } from '../lib/types';
	import { STATUS_COLOR, PRIORITY_COLOR } from '../lib/colors';
	import { bucketByDueDate } from '../lib/buckets';
	import { computeStats } from '../lib/stats';
	import { summarizeNotification } from '../lib/notifications';
	import {
		myTasks, labels, workstreams, notifications,
		loadMyWork, teardownMyWork, loadNotifications, addTask, openTask, openNotification
	} from '../lib/store';

	const now = Date.now();
	const startToday = new Date(now).setHours(0, 0, 0, 0);
	const endToday = startToday + 86_399_999;

	const STATUS_SHAPE: Record<TaskStatus, 'dashed' | 'ring' | 'half' | 'check' | 'x'> = {
		backlog: 'dashed', todo: 'ring', in_progress: 'half', in_review: 'half', done: 'check', canceled: 'x'
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

	// ---- Theme toggle ----
	let dark = false;
	function toggleTheme() {
		dark = !dark;
		const v = dark ? 'dark' : 'light';
		try { localStorage.setItem('theme', v); } catch { /* ignore */ }
		appTheme.set(v);
		document.documentElement.classList.toggle('dark', dark);
	}

	onMount(() => { dark = document.documentElement.classList.contains('dark'); void loadMyWork(); void loadNotifications(); });
	onDestroy(() => teardownMyWork());

	$: uid = $user?.id ?? '';
	$: firstName = ($user?.name ?? 'there').split(' ')[0];
	$: dateLine = `${new Date(now).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })} · ${buckets.today.length} task${buckets.today.length === 1 ? '' : 's'} due today across your Workstreams.`;

	$: openTasks = $myTasks.filter((t) => t.status !== 'done' && t.status !== 'canceled');
	$: buckets = bucketByDueDate(openTasks, now);
	$: openStats = computeStats(openTasks, now);
	$: doneThisWeek = computeStats($myTasks, now).doneThisWeek;

	$: stats4 = [
		{ value: $myTasks.filter((t) => (t.assignee_ids ?? []).includes(uid)).length, label: 'Assigned to you', icon: 'list',
			chip: 'bg-brand-100 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200' },
		{ value: buckets.today.length + buckets.thisWeek.length, label: 'Due this week', icon: 'clock',
			chip: 'bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-400' },
		{ value: $myTasks.filter((t) => t.status === 'in_review').length, label: 'Waiting on review', icon: 'message-square',
			chip: 'bg-purple-50 text-purple-600 dark:bg-purple-500/15 dark:text-purple-300' },
		{ value: doneThisWeek, label: 'Done this week', icon: 'circle-check',
			chip: 'bg-green-50 text-green-600 dark:bg-green-500/15 dark:text-green-400' }
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
	$: filtered = (wsFilter === 'all' ? openTasks : openTasks.filter((t) => t.workstream_id === wsFilter))
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

	const labelsFor = (t: Task): Label[] => (t.labels ?? []).map((id) => $labels.find((l) => l.id === id)).filter((l): l is Label => !!l);
	const wsName = (t: Task) => $workstreams.find((w) => w.id === t.workstream_id)?.name ?? '';
	function dueClass(t: Task): string {
		if (t.due_date == null) return 'text-gray-400';
		if (t.due_date < startToday) return 'text-red-500';
		if (t.due_date <= endToday) return 'text-primary';
		return 'text-gray-400';
	}

	// New task (cross-workstream).
	let creating = false, newTitle = '', target = '';
	$: defaultStream = [...$myTasks].sort((a, b) => b.updated_at - a.updated_at)[0]?.workstream_id ?? $workstreams[0]?.id ?? '';
	$: if (!target) target = defaultStream;
	async function submitNew() {
		if (!newTitle.trim() || !target) return;
		await addTask(target, { title: newTitle.trim() });
		newTitle = ''; creating = false;
	}

	const CARD = 'border border-gray-200 dark:border-gray-800 rounded-[7px] bg-white dark:bg-gray-900 shadow-sm';
</script>

<div class="h-full overflow-auto bg-white dark:bg-gray-950">
	<div class="max-w-[1240px] mx-auto px-9 pt-7 pb-14">

		<!-- Header -->
		<div class="flex items-center gap-4 mb-6">
			<div class="flex-1 min-w-0">
				<h1 class="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">{greetWord()}, {firstName}</h1>
				<p class="mt-1 text-sm text-gray-400 dark:text-gray-500">{dateLine}</p>
			</div>
			<button type="button" onclick={toggleTheme} class="inline-flex items-center gap-1.5 h-[34px] px-3 rounded-[5px] border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-300 text-sm font-medium hover:bg-gray-50 dark:hover:bg-gray-800 shadow-sm">
				<Icon name={dark ? 'sun' : 'moon'} size={16} /> {dark ? 'Light' : 'Dark'}
			</button>
			{#if creating}
				<select class="text-sm h-[34px] rounded-[5px] border border-gray-300 dark:border-gray-700 bg-transparent px-2" bind:value={target}>
					{#each $workstreams as s (s.id)}<option value={s.id}>{s.name}</option>{/each}
				</select>
				<input
					class="text-sm h-[34px] px-3 rounded-[5px] border border-gray-300 dark:border-gray-700 bg-transparent w-44"
					placeholder="Task title…"
					bind:value={newTitle}
					onkeydown={(e) => { if (e.key === 'Enter') submitNew(); if (e.key === 'Escape') { creating = false; newTitle = ''; } }}
					autofocus
				/>
			{:else}
				<button type="button" onclick={() => (creating = true)} class="inline-flex items-center gap-1.5 h-[34px] px-3.5 rounded-[5px] bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 shadow-sm">
					<Icon name="plus" size={16} /> New task
				</button>
			{/if}
		</div>

		<!-- Stat tiles -->
		<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-[18px]">
			{#each stats4 as s (s.label)}
				<div class="flex items-center gap-3.5 px-[18px] py-4 {CARD}">
					<span class="w-10 h-10 rounded-[7px] flex items-center justify-center flex-none {s.chip}"><Icon name={s.icon} size={19} /></span>
					<div>
						<div class="text-3xl font-semibold tracking-tight leading-none tabular-nums text-gray-900 dark:text-gray-100">{s.value}</div>
						<div class="text-[13px] text-gray-400 dark:text-gray-500 mt-1.5">{s.label}</div>
					</div>
				</div>
			{/each}
		</div>

		<!-- Overdue callout -->
		{#if overdue.length}
			<div class="flex items-center gap-3.5 px-4 py-3.5 border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/40 rounded-[7px] mb-[18px]">
				<span class="w-8 h-8 rounded-full bg-red-500 text-white flex items-center justify-center flex-none"><Icon name="alert-triangle" size={17} /></span>
				<div class="flex-1 min-w-0">
					<div class="text-sm font-semibold text-red-700 dark:text-red-300">{overdue.length} task{overdue.length === 1 ? ' is' : 's are'} overdue</div>
					<div class="text-xs text-red-700/80 dark:text-red-300/80 mt-px truncate">{overdue.map((t) => t.title).join(' · ')}</div>
				</div>
				<button type="button" onclick={() => openTask(overdue[0].id)} class="text-xs font-medium px-3 h-7 rounded-[5px] border border-red-300 dark:border-red-800 text-red-700 dark:text-red-300 hover:bg-white/70 dark:hover:bg-red-950/60">Review now</button>
			</div>
		{/if}

		<!-- Bento grid -->
		<div class="grid grid-cols-1 lg:grid-cols-[1.55fr_1fr] gap-[18px] items-start">

			<!-- LEFT: filtered task list -->
			<div class="{CARD} overflow-hidden">
				<div class="px-[18px] pt-4 pb-3.5 border-b border-gray-100 dark:border-gray-800">
					<div class="flex items-center gap-3 mb-3">
						<span class="flex-1 text-[17px] font-semibold tracking-tight text-gray-900 dark:text-gray-100">My tasks</span>
						<span class="font-mono text-xs text-gray-400">{filtered.length} shown</span>
					</div>
					<div class="flex gap-2 flex-wrap">
						{#each wsChips as c (c.id)}
							<button
								type="button"
								onclick={() => (wsFilter = c.id)}
								class="h-7 px-3 rounded-full text-[13px] font-medium border transition-colors
									{wsFilter === c.id
										? 'border-brand-300 bg-brand-100 text-primary dark:border-brand-700 dark:bg-brand-900/40 dark:text-brand-200'
										: 'border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'}"
							>{c.name}</button>
						{/each}
					</div>
				</div>
				<div class="px-2.5 pt-1.5 pb-2.5">
					{#if !filtered.length}
						<div class="py-14 text-center text-sm text-gray-400">Nothing on your plate here.</div>
					{:else}
						{#each filtered as t (t.id)}
							<button type="button" onclick={() => openTask(t.id)} class="w-full text-left px-2 pt-2.5 pb-3 rounded-[5px] hover:bg-gray-50 dark:hover:bg-gray-800/60 transition-colors">
								<div class="flex items-center gap-[11px]">
									<StatusDot shape={STATUS_SHAPE[t.status]} color={STATUS_COLOR[t.status]} size={16} />
									<PriorityIcon priority={t.priority} size={15} />
									<span class="font-mono text-[11px] text-gray-400 flex-none">{t.key}</span>
									<span class="flex-1 min-w-0 text-[15px] text-gray-900 dark:text-gray-100 truncate">{t.title}</span>
									<span class="font-mono text-xs flex-none {dueClass(t)}">{t.due_date ? fmtDue(t.due_date) : '—'}</span>
								</div>
								<div class="flex items-center gap-2 mt-[9px] pl-[27px]">
									{#each labelsFor(t) as lb (lb.id)}<Pills label={lb} />{/each}
									<span class="text-[11px] text-gray-400 inline-flex items-center gap-1">
										<span class="w-1.5 h-1.5 rounded-full bg-brand-500"></span>{wsName(t)}
									</span>
									<span class="flex-1"></span>
									{#if t.progress > 0}
										<span class="inline-flex items-center gap-2 w-[130px]">
											<span class="flex-1 h-1.5 bg-gray-200 dark:bg-gray-800 rounded-full overflow-hidden"><span class="block h-full bg-primary rounded-full" style="width:{t.progress}%"></span></span>
											<span class="font-mono text-[11px] text-gray-400 w-7 text-right">{t.progress}%</span>
										</span>
									{/if}
								</div>
							</button>
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
									<span class="font-mono text-[13px] font-medium text-gray-900 dark:text-gray-100">{seg.n}</span>
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
									<div class="font-mono text-[11px] text-gray-400">{d.date}</div>
								</div>
								<div class="w-px self-stretch bg-gray-100 dark:bg-gray-800"></div>
								<div class="flex-1 min-w-0 flex items-center gap-2">
									<PriorityIcon priority={d.task.priority} size={14} />
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
									<b class="font-medium text-gray-900 dark:text-gray-100">{a.first}</b> {a.action}{#if a.target} <span class="font-mono text-xs text-primary">{a.target}</span>{/if}{#if a.detail} {a.detail}{/if}
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
						{#if unreadMentions}<span class="font-mono text-[11px] text-white bg-red-500 rounded-full px-1.5 py-0.5">{unreadMentions}</span>{/if}
					</div>
					{#if !mentions.length}
						<div class="text-xs text-gray-400 py-1">No mentions.</div>
					{:else}
						{#each mentions as m (m.id)}
							<button type="button" onclick={() => openNotification(m)} class="w-full text-left flex items-start gap-2.5 py-[7px]">
								<Avatar name={m.data?.actor_name ?? '?'} size={22} />
								<div class="flex-1 min-w-0">
									<div class="text-[13px] text-gray-600 dark:text-gray-300 leading-snug">{m.data?.snippet ?? summarizeNotification(m)}</div>
									<div class="font-mono text-[11px] text-gray-400 mt-0.5">{m.data?.task_key ?? ''} · {ago(m.created_at)}</div>
								</div>
							</button>
						{/each}
					{/if}
				</div>

			</div>
		</div>
	</div>
</div>
