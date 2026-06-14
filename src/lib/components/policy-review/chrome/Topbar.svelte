<script lang="ts">
	// Top bar: breadcrumb + right-side action buttons.
	// Port of the topbar block from the design's app.jsx.

	import Icon from '../ui/Icon.svelte';
	import { view, stage, resetReview, canUseChecker } from '../lib/store';
	import { POLICY_META } from '../lib/mocks';

	function startNewReview() {
		resetReview();
		view.set('new-review');
	}

	// Mock — sync state. In a later phase this reads a real store backed by
	// the ingestion pipeline (sources: Etimad, SharePoint, Drive).
	const syncedMinutesAgo = 14;
	const stale = syncedMinutesAgo > 60 * 24;
	const syncLabel =
		syncedMinutesAgo < 60
			? `Synced ${syncedMinutesAgo}m ago`
			: `Synced ${Math.round(syncedMinutesAgo / 60)}h ago`;
</script>

<div class="topbar">
	<div class="tb-title">
		<span class="sb-brand-dot" style="width:24px; height:24px">
			<Icon name="grid" size={13} stroke={2.4} />
		</span>
		<span class="crumb">Osool AI</span>
		<Icon name="chevR" size={12} />
		<span class="name">
			{#if $view === 'all-policies'}
				All policies
			{:else if $stage === 'upload'}
				Policy Review
			{:else}
				{POLICY_META.name}
			{/if}
		</span>
	</div>

	<div class="tb-actions">
		<span
			class="pl-topbar-sync"
			class:stale
			title={stale
				? 'Last sync over 24h ago — see runbook'
				: 'Sources: Etimad · SharePoint · Drive'}
		>
			<span class="dot" aria-hidden="true"></span>
			{syncLabel}
		</span>
		{#if $canUseChecker && $view === 'new-review' && $stage === 'review'}
			<button class="btn btn-sm" onclick={startNewReview} type="button">
				<Icon name="refresh" size={12} /> New review
			</button>
			<button class="btn btn-sm" type="button">
				<Icon name="download" size={12} /> Export
			</button>
		{/if}
	</div>
</div>
