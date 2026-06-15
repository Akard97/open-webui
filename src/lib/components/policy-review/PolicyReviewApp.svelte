<script lang="ts">
	// Top-level Policy Review composition. Mirrors app.jsx from the
	// design handoff: ToolSidebar + Topbar + active view, plus the
	// item drawer and submit-for-approval modal as fixed overlays.

	import { onMount, onDestroy, untrack } from 'svelte';
	import ToolSidebar from './chrome/ToolSidebar.svelte';
	import Topbar from './chrome/Topbar.svelte';
	import AllPoliciesView from './views/AllPoliciesView.svelte';
	import UploadView from './views/UploadView.svelte';
	import ScanningView from './views/ScanningView.svelte';
	import ReviewView from './views/ReviewView.svelte';
	import OverviewView from './views/OverviewView.svelte';
	import MyReviewsView from './views/MyReviewsView.svelte';
	import ApprovalQueueView from './views/ApprovalQueueView.svelte';
	import AdminApp from './views/admin/AdminApp.svelte';
	import ItemDrawer from './views/ItemDrawer.svelte';
	import SubmitApprovalModal from './views/SubmitApprovalModal.svelte';
	import PolicyPopup from './views/PolicyPopup.svelte';
	import {
		view,
		stage,
		activeVersion,
		activeReview,
		drawerOpen,
		picked,
		canUseChecker,
		canApprove,
		canAdmin,
		loadAll
	} from './lib/store';

	// Snap users away from views their permissions don't allow, or a review view
	// with nothing selected. Library + Overview are open to everyone.
	$: if (($view === 'new-review' || $view === 'my-reviews') && !$canUseChecker) view.set('overview');
	$: if ($view === 'approvals' && !$canApprove) view.set('overview');
	$: if ($view === 'review' && !$activeReview) view.set('overview');
	$: if ($view === 'admin' && !$canAdmin) view.set('overview');

	function handleKey(e: KeyboardEvent) {
		const p = untrack(() => $picked);
		if (e.key === 'Escape' && untrack(() => $drawerOpen)) {
			drawerOpen.set(false);
			return;
		}
		if (!untrack(() => $drawerOpen) || !p) return;
		if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
			e.preventDefault();
			const flat: { sectionId: string; n: number }[] = [];
			untrack(() => $activeVersion)?.sections.forEach((sec) =>
				sec.items.forEach((it) => flat.push({ sectionId: sec.id, n: it.n }))
			);
			const idx = flat.findIndex((f) => f.sectionId === p.sectionId && f.n === p.n);
			if (idx === -1) return;
			const next =
				e.key === 'ArrowRight'
					? (idx + 1) % flat.length
					: (idx - 1 + flat.length) % flat.length;
			picked.set(flat[next]);
		}
	}

	onMount(() => {
		loadAll();
		window.addEventListener('keydown', handleKey);
	});
	onDestroy(() => window.removeEventListener('keydown', handleKey));
</script>

<div class="app">
	<ToolSidebar />
	<main class="main">
		<Topbar />
		<div class="canvas">
			{#if $view === 'overview'}
				<OverviewView />
			{:else if $view === 'library'}
				<AllPoliciesView />
			{:else if $view === 'my-reviews'}
				<MyReviewsView />
			{:else if $view === 'approvals'}
				<ApprovalQueueView />
			{:else if $view === 'new-review'}
				{#if $stage === 'upload'}
					<UploadView />
				{:else}
					<ScanningView />
				{/if}
			{:else if $view === 'admin'}
				<AdminApp />
			{:else}
				<ReviewView />
			{/if}
		</div>
	</main>

	<ItemDrawer />
	<SubmitApprovalModal />
	<PolicyPopup />
</div>
