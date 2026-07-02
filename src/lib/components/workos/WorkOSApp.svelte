<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import './styles.css';
	import Sidebar from './chrome/Sidebar.svelte';
	import Topbar from './chrome/Topbar.svelte';
	import BoardView from './views/BoardView.svelte';
	import ListView from './views/ListView.svelte';
	import OverviewView from './views/OverviewView.svelte';
	import CalendarView from './views/CalendarView.svelte';
	import TaskDetail from './views/TaskDetail.svelte';
	import AdminApp from './views/admin/AdminApp.svelte';
	import AccessConsole from './views/access/AccessConsole.svelte';
	import InboxView from './views/InboxView.svelte';
	import MyWorkView from './views/MyWorkView.svelte';
	import ModalHost from './views/ModalHost.svelte';
	import { canUseAdmin, canUseAccessConsole } from './lib/roles';
	import { user } from '$lib/stores';
	import {
		loadBootstrap, connectRealtime, disconnectRealtime,
		view, selectedTask, teams, roles, loading
	} from './lib/store';

	// Guard: snap non-admins away from the admin view.
	$: if ($view === 'admin' && !canUseAdmin($user)) view.set('board');
	// Guard: the access console is for team owners/admins and system admins only.
	// Skip while roles are still loading so a slow bootstrap doesn't bounce the view.
	$: if ($view === 'access' && $teams.length && !canUseAccessConsole($user, $roles)) view.set('board');

	onMount(async () => {
		await loadBootstrap();
		connectRealtime();
	});
	onDestroy(() => disconnectRealtime());
</script>

<div class="workos-root text-gray-800 dark:text-gray-100">
	<Sidebar />
	<div class="flex-1 flex flex-col min-w-0">
		<!-- Topbar is workstream chrome (title + tabs); global views (My Work, Inbox, Admin) carry their own header. -->
		{#if $view === 'board' || $view === 'list' || $view === 'calendar' || $view === 'overview'}
			<Topbar />
		{/if}
		<div class="flex-1 relative min-h-0 bg-gray-50 dark:bg-gray-900">
			{#if $loading && !$teams.length}
				<div class="h-full flex items-center justify-center text-sm text-gray-400">Loading…</div>
			{:else if $view === 'admin'}
				<AdminApp />
			{:else if $view === 'access'}
				<AccessConsole />
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
			{:else}
				<BoardView />
			{/if}
			{#if $selectedTask}
				<TaskDetail />
			{/if}
		</div>
	</div>
	<ModalHost />
</div>
