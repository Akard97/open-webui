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
	import ItemDrawer from './views/ItemDrawer.svelte';
	import SubmitApprovalModal from './views/SubmitApprovalModal.svelte';
	import PolicyPopup from './views/PolicyPopup.svelte';
	import { view, stage, sections, drawerOpen, picked, canUseChecker } from './lib/store';

	// Users without checker access only get the Library; snap them back if a stale persisted
	// view/stage would otherwise drop them into the checker workflow.
	$: if (!$canUseChecker && $view !== 'all-policies') view.set('all-policies');

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
			untrack(() => $sections).forEach((sec) =>
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

	onMount(() => window.addEventListener('keydown', handleKey));
	onDestroy(() => window.removeEventListener('keydown', handleKey));
</script>

<div class="app">
	<ToolSidebar />
	<main class="main">
		<Topbar />
		<div class="canvas">
			{#if $view === 'all-policies'}
				<AllPoliciesView />
			{:else if $stage === 'upload'}
				<UploadView />
			{:else if $stage === 'scanning'}
				<ScanningView />
			{:else}
				<ReviewView />
			{/if}
		</div>
	</main>

	<ItemDrawer />
	<SubmitApprovalModal />
	<PolicyPopup />
</div>
