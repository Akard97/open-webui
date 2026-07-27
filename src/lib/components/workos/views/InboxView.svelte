<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { mobile } from '$lib/stores';
	import Icon from '../ui/Icon.svelte';
	import EmptyState from '../ui/EmptyState.svelte';
	import NeedsYouCard from './inbox/NeedsYouCard.svelte';
	import FeedRow from './inbox/FeedRow.svelte';
	import TaskDetailBody from './detail/TaskDetailBody.svelte';
	import { groupInbox } from '../lib/inbox';
	import { agoShort } from '../lib/inboxFormat';
	import type { Notification, NotificationType } from '../lib/types';
	import {
		notifications, archivedNotifications, notificationCounts, notificationsHasMore, archivedHasMore,
		selectedTaskId, selectedTask, inboxTaskError, inboxTaskLoadError, inboxSplit,
		loadNotifications, loadMoreNotifications, loadArchivedNotifications, loadMoreArchivedNotifications,
		markRead, markAllRead, archiveNotificationsAction, archiveAllRead,
		openInboxNotification, openNotification, closeTask
	} from '../lib/store';

	let now = Date.now();

	onMount(() => {
		void loadNotifications();
		const tick = setInterval(() => (now = Date.now()), 60_000); // keep day labels + ages fresh
		return () => {
			clearInterval(tick);
			// Desktop: leaving the inbox clears the split-pane selection. Mobile taps
			// navigate away (openNotification → view 'board'), which unmounts this
			// view — that selection must survive the unmount or the full-screen
			// task dialog would be closed before it ever opens.
			if (!$mobile) closeTask();
		};
	});

	type Tab = 'all' | NotificationType;
	const TABS: { k: Tab; label: string }[] = [
		{ k: 'all', label: 'All' },
		{ k: 'mentioned', label: 'Mentions' },
		{ k: 'assigned', label: 'Assigned' },
		{ k: 'commented', label: 'Comments' },
		{ k: 'status_changed', label: 'Status' }
	];
	let tab: Tab = 'all';
	let unreadOnly = false;
	let showArchived = false;

	function toggleArchived(): void {
		showArchived = !showArchived;
		unreadOnly = false; // archived rows are always read — a stale unread filter would blank the list
		if (showArchived) void loadArchivedNotifications();
	}

	$: counts = $notificationCounts;
	$: tabCount = (k: Tab) =>
		k === 'all'
			? counts.unread
			: k === 'assigned'
				? (counts.by_type.assigned ?? 0) + (counts.by_type.subtask_assigned ?? 0)
				: (counts.by_type[k] ?? 0);
	$: source = showArchived ? $archivedNotifications : $notifications;
	$: filtered = source.filter(
		(n) =>
			(tab === 'all' || n.type === tab || (tab === 'assigned' && n.type === 'subtask_assigned')) &&
			(!unreadOnly || !n.read)
	);
	$: groups = groupInbox(filtered, now);

	$: needsCount =
		counts.by_type.mentioned + counts.by_type.assigned + (counts.by_type.subtask_assigned ?? 0);
	$: updatesCount = Math.max(0, counts.unread - needsCount);
	$: oldestUnread = [...$notifications].reverse().find((n) => !n.read);

	// Selection is per-notification (not per-task): several rows can share a task
	// and must not all light up. Cleared when the pane selection closes.
	let selectedNotifId: string | null = null;
	$: if (!$selectedTaskId) selectedNotifId = null;

	// 768–1279px: no split pane, so a 404'd/deleted task (inboxTaskError) has no
	// EmptyState to render into — WorkOSApp's dialog either stays closed (silent
	// dead-end click) or would resolve a stale `myTasks` copy. Surface it with a
	// toast and close the (possibly stale) dialog. closeTask() resets
	// inboxTaskError, so this disarms itself — runs once per error. Desktop
	// (inboxSplit) keeps its own EmptyState untouched.
	$: if ($inboxTaskError && !$inboxSplit) {
		toast.error('Task no longer available');
		closeTask();
	}

	// Transient load failure at mid-width: if a local copy resolves, the dialog
	// still works — stay quiet. Otherwise the click is a dead end: say it's
	// retryable (unlike the "gone" toast above) and close so a re-click retries.
	$: if ($inboxTaskLoadError && !$inboxSplit && !$selectedTask) {
		toast.error("Couldn't load the task — try again");
		closeTask();
	}

	// Split-pane retry for a transient load failure: re-open the selected
	// notification (openInboxNotification resets both error flags itself).
	function retryLoad(): void {
		const n =
			source.find((x) => x.id === selectedNotifId) ??
			source.find((x) => x.task_id === $selectedTaskId);
		if (n) void openInboxNotification(n);
	}

	// ≥1280px: split pane. 768–1279px: same selection flow, but WorkOSApp renders
	// the task dialog over the inbox (no view switch — highlight + realtime intact).
	// Mobile: old navigate-away flow.
	function open(n: Notification): void {
		if ($mobile) {
			void openNotification(n);
		} else {
			selectedNotifId = n.id;
			void openInboxNotification(n);
		}
	}
	const read = (n: Notification) =>
		void markRead([n.id]).catch(() => toast.error("Couldn't update — try again"));
	const archive = (n: Notification) =>
		void archiveNotificationsAction([n.id], !showArchived).catch(() =>
			toast.error("Couldn't update — try again")
		);
</script>

<div class="flex h-full min-h-0">
	<!-- ─────────── left: list pane ───────────
	     Full-width below xl (no split pane — selection opens the dialog instead;
	     sidebar 256px + list would leave a useless sliver). At ≥xl the list is
	     fixed-width so the detail pane gets every remaining pixel
	     (TaskDetailBody stacks below an 880px container width). -->
	<div class="flex w-full min-w-0 flex-col border-r border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950 xl:w-[400px] xl:flex-none 2xl:w-[440px]">
		<!-- header -->
		<div class="px-4 pt-4">
			<h1 class="text-[22px] font-semibold tracking-tight text-gray-900 dark:text-gray-100">
				{showArchived ? 'Archived' : 'Inbox'}
			</h1>
			{#if !showArchived}
				<p class="wos-body mt-0.5 text-gray-400 dark:text-gray-500">
					{#if counts.unread === 0}
						You're all caught up.
					{:else}
						<span class="font-semibold text-gray-600 dark:text-gray-300">{needsCount} need{needsCount === 1 ? 's' : ''} your attention</span>
						· {updatesCount} more update{updatesCount === 1 ? '' : 's'}
						{#if oldestUnread}· oldest unread {agoShort(oldestUnread.created_at, now)}{/if}
					{/if}
				</p>
			{:else}
				<p class="wos-body mt-0.5 text-gray-400 dark:text-gray-500">Archived notifications — unarchive to move them back.</p>
			{/if}
		</div>
		<!-- controls -->
		<div class="flex flex-wrap items-center gap-2 border-b border-gray-100 px-4 py-3 dark:border-gray-900">
			<div class="flex min-w-0 max-w-full shrink gap-0.5 overflow-x-auto rounded-full bg-gray-100 p-[3px] dark:bg-gray-900">
				{#each TABS as t (t.k)}
					<button
						class="flex flex-none items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1 text-xs font-medium transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none
							{tab === t.k
								? 'bg-white font-semibold text-gray-900 shadow-sm dark:bg-gray-850 dark:text-gray-100'
								: 'text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200'}"
						onclick={() => (tab = t.k)}
					>
						{t.label}
						{#if !showArchived && tabCount(t.k) > 0}
							<span class="min-w-4 rounded-full px-1 text-center text-[10px] font-semibold tabular-nums
								{tab === t.k ? 'bg-primary text-primary-foreground' : 'bg-gray-200 text-gray-600 dark:bg-gray-800 dark:text-gray-300'}">{tabCount(t.k)}</span>
						{/if}
					</button>
				{/each}
			</div>
			<div class="flex-1"></div>
			{#if !showArchived}
				<button
					type="button" role="switch" aria-checked={unreadOnly}
					class="inline-flex h-7 items-center gap-1.5 rounded-[10px] border pl-2.5 pr-1.5 text-xs font-medium transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none
						{unreadOnly
							? 'border-primary/40 bg-primary/10 text-primary'
							: 'border-gray-200 text-gray-600 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-850'}"
					onclick={() => (unreadOnly = !unreadOnly)}
				>
					Unread only
					<span class="relative inline-block h-[15px] w-[26px] rounded-full transition-colors duration-150 {unreadOnly ? 'bg-primary' : 'bg-gray-300 dark:bg-gray-700'}">
						<span class="absolute top-0.5 h-[11px] w-[11px] rounded-full bg-white shadow transition-transform duration-150 {unreadOnly ? 'translate-x-[13px]' : 'translate-x-0.5'}"></span>
					</span>
				</button>
			{/if}
			<button
				class="flex h-7 items-center gap-1.5 rounded-[10px] border px-2.5 text-xs font-medium transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none
					{showArchived
						? 'border-primary/40 bg-primary/10 text-primary'
						: 'border-gray-200 text-gray-600 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-850'}"
				title={showArchived ? 'Back to inbox' : 'Archived'}
				onclick={toggleArchived}
			>
				<Icon name={showArchived ? 'arrow-left' : 'archive'} size={13} />
				{showArchived ? 'Back' : 'Archived'}
			</button>
			{#if !showArchived && counts.unread > 0}
				<button
					class="flex h-7 items-center gap-1.5 rounded-[10px] border border-gray-200 px-2.5 text-xs font-medium text-gray-600 transition-colors duration-150 hover:bg-gray-50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-850"
					onclick={() => void markAllRead().catch(() => toast.error("Couldn't update — try again"))}
				>
					<Icon name="check" size={13} /> Mark all read
				</button>
			{/if}
			{#if !showArchived && $notifications.some((n) => n.read)}
				<button
					class="flex h-7 items-center gap-1.5 rounded-[10px] border border-gray-200 px-2.5 text-xs font-medium text-gray-600 transition-colors duration-150 hover:bg-gray-50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-850"
					title="Archive all read"
					onclick={() => void archiveAllRead().catch(() => toast.error("Couldn't update — try again"))}
				>
					<Icon name="archive" size={13} /> Sweep read
				</button>
			{/if}
		</div>
		<!-- scroll region -->
		<div class="min-h-0 flex-1 overflow-y-auto pb-6">
			{#if !filtered.length}
				<EmptyState
					icon="inbox"
					title={showArchived ? 'Nothing archived' : unreadOnly || tab !== 'all' ? 'Nothing here' : "You're all caught up"}
					sub={showArchived ? 'Archived notifications will show up here.' : 'Mentions, assignments and updates will show up here.'}
				/>
			{:else}
				{#if !showArchived && groups.needsYou.length}
					<div class="flex items-center gap-2 px-4 pb-2 pt-4">
						<span class="text-primary"><Icon name="at-sign" size={14} /></span>
						<span class="wos-body font-medium text-gray-600 dark:text-gray-300">Needs you</span>
						<span class="rounded-full bg-primary/10 px-2 text-[11px] font-semibold text-primary">{groups.needsYou.length}</span>
					</div>
					{#each groups.needsYou as n (n.id)}
						<NeedsYouCard
							{n}
							selected={$inboxSplit && selectedNotifId === n.id}
							onopen={() => open(n)}
							onread={() => read(n)}
							onarchive={() => archive(n)}
						/>
					{/each}
				{/if}
				{#each groups.days as day (day.label)}
					<div class="flex items-center gap-2.5 px-4 pb-1.5 pt-4">
						<span class="wos-caption font-semibold uppercase tracking-[0.06em] text-gray-400 dark:text-gray-500">{day.label}</span>
						<span class="h-px flex-1 bg-gray-100 dark:bg-gray-900"></span>
					</div>
					{#each day.entries as entry (entry.latest.id)}
						<FeedRow
							{entry}
							archivedView={showArchived}
							selectedId={$inboxSplit ? selectedNotifId : null}
							onopen={open}
							onread={read}
							onarchive={archive}
						/>
					{/each}
				{/each}
			{/if}
			<!-- Outside the empty-check: a filter can empty the LOADED page while older
			     matches exist on the server — pagination must stay reachable. -->
			{#if showArchived ? $archivedHasMore : $notificationsHasMore}
				<button
					class="mx-4 mt-3 flex h-8 w-[calc(100%-2rem)] items-center justify-center rounded-lg border border-gray-200 text-xs font-medium text-gray-500 transition-colors duration-150 hover:bg-gray-50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:border-gray-800 dark:text-gray-400 dark:hover:bg-gray-850"
					onclick={() => void (showArchived ? loadMoreArchivedNotifications() : loadMoreNotifications())}
				>Load more</button>
			{/if}
		</div>
	</div>
	<!-- ─────────── right: detail pane (≥1280px only) ───────────
	     Error checked BEFORE the body: a deleted/404 task can still resolve a
	     stale copy from `myTasks`, which must not render over the error state. -->
	{#if $inboxSplit}
		<div class="flex min-w-0 flex-1 flex-col bg-white dark:bg-gray-950">
			{#if $selectedTaskId && $inboxTaskError}
				<EmptyState icon="inbox" title="Task no longer available" sub="It may have been deleted, or you no longer have access to it." />
			{:else if $selectedTask}
				<TaskDetailBody />
			{:else if $selectedTaskId && $inboxTaskLoadError}
				<!-- After $selectedTask on purpose: a usable local copy beats the error. -->
				<EmptyState icon="inbox" title="Couldn't load the task" sub="Something went wrong on the way — the task itself is still there." ctaLabel="Try again" onCta={retryLoad} />
			{:else if $selectedTaskId}
				<div class="flex h-full items-center justify-center text-sm text-gray-400">Loading…</div>
			{:else}
				<EmptyState icon="message-square" title="Select a notification" sub="The task opens here so you keep your place in the inbox." />
			{/if}
		</div>
	{/if}
</div>
