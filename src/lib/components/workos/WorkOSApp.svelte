<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import './styles.css';
	import Sidebar from './chrome/Sidebar.svelte';
	import Topbar from './chrome/Topbar.svelte';
	import MobileHeader from './chrome/MobileHeader.svelte';
	import NavDrawer from './chrome/NavDrawer.svelte';
	import BoardView from './views/BoardView.svelte';
	import ListView from './views/ListView.svelte';
	import OverviewView from './views/OverviewView.svelte';
	import CalendarView from './views/CalendarView.svelte';
	import TimelineView from './views/TimelineView.svelte';
	import FilesView from './views/FilesView.svelte';
	import TaskDetail from './views/TaskDetail.svelte';
	import AdminApp from './views/admin/AdminApp.svelte';
	import InboxView from './views/InboxView.svelte';
	import MyWorkView from './views/MyWorkView.svelte';
	import ModalHost from './views/ModalHost.svelte';
	import TaskCreateDialog from './views/TaskCreateDialog.svelte';
	import TeamSettingsDialog from './chrome/access/TeamSettingsDialog.svelte';
	import WorkspaceSettingsDialog from './chrome/access/WorkspaceSettingsDialog.svelte';
	import { canUseAdmin } from './lib/roles';
	import { user, mobile } from '$lib/stores';
	import {
		loadBootstrap, connectRealtime, disconnectRealtime,
		view, selectedTask, teams, loading, mobileNavOpen, inboxSplit
	} from './lib/store';
	import { hydrateFromUrl, initUrlSync, destroyUrlSync, urlHasWorkstream } from './lib/urlSync';
	import { track } from '$lib/utils/usage';

	// Guard: snap non-admins away from the admin view.
	$: if ($view === 'admin' && !canUseAdmin($user)) view.set('board');

	// Crossing back to desktop must not leave a phantom drawer overlay.
	$: if (!$mobile) mobileNavOpen.set(false);

	// Guards the onMount chain below: if the user navigates away from /workos
	// while loadBootstrap/hydrateFromUrl is still in flight, the orphaned
	// continuation must not call initUrlSync()/connectRealtime() on a route
	// nobody is looking at anymore.
	let destroyed = false;

	// Tracks WorkOS view switches (board/list/calendar/etc.) once the view
	// store settles past its initial value — skips the emission that fires
	// merely from subscribing.
	let firstView = true;
	const unsubView = view.subscribe((v) => {
		if (firstView) {
			firstView = false;
			return;
		}
		track('workos.view.switch', { view: v });
	});
	onDestroy(unsubView);

	onMount(async () => {
		// Deep link present → hydrateFromUrl performs the one workstream
		// selection; otherwise bootstrap picks its default as before.
		await loadBootstrap({ selectDefaultWorkstream: !urlHasWorkstream() });
		if (destroyed) return;
		await hydrateFromUrl();
		if (destroyed) return;
		initUrlSync();
		connectRealtime();
	});
	onDestroy(() => {
		destroyed = true;
		destroyUrlSync();
		disconnectRealtime();
	});
</script>

<div class="workos-root text-gray-800 dark:text-gray-100">
	{#if !$mobile}
		<Sidebar />
	{/if}
	<div class="flex-1 flex flex-col min-w-0">
		<!-- Mobile: WorkOS header row under the global app bar (mirrors the chat tool's
		     pattern) — its toggle opens the nav drawer. -->
		{#if $mobile}
			<MobileHeader />
		{/if}
		<!-- Topbar is workstream chrome (title + tabs); global views (My Work, Inbox, Admin) carry their own header. -->
		{#if $view === 'board' || $view === 'list' || $view === 'calendar' || $view === 'overview' || $view === 'timeline' || $view === 'files'}
			<Topbar />
		{/if}
		<div class="flex-1 relative min-h-0 bg-gray-50 dark:bg-gray-900">
			{#if $loading && !$teams.length}
				<div class="h-full flex items-center justify-center text-sm text-gray-400">Loading…</div>
			{:else if $view === 'admin'}
				<AdminApp />
			{:else if $view === 'inbox'}
				<InboxView />
			{:else if $view === 'mywork'}
				<MyWorkView />
			{:else if !$teams.length}
				<div class="h-full flex flex-col items-center justify-center gap-2 text-center px-6">
					<div class="text-lg font-medium">You're not in any teams yet</div>
					<div class="text-sm text-gray-500">Create a team from the sidebar to get started.</div>
				</div>
			{:else if $view === 'overview'}
				<OverviewView />
			{:else if $view === 'list'}
				<ListView />
			{:else if $view === 'calendar'}
				<CalendarView />
			{:else if $view === 'timeline'}
				<TimelineView />
			{:else if $view === 'files'}
				<FilesView />
			{:else}
				<BoardView />
			{/if}
			{#if $selectedTask && !($view === 'inbox' && $inboxSplit)}
				<TaskDetail />
			{/if}
		</div>
	</div>
	{#if $mobile}
		<NavDrawer />
	{/if}
	<ModalHost />
	<TaskCreateDialog />
	<TeamSettingsDialog />
	<WorkspaceSettingsDialog />
</div>
