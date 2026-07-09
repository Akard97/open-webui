<script lang="ts">
	// Top bar: breadcrumb + right-side action buttons.
	// Port of the topbar block from the design's app.jsx.

	import Icon from '../ui/Icon.svelte';
	import { WEBUI_NAME } from '$lib/stores';
	import { view, stage, goNewReview, canUseChecker, activeReview } from '../lib/store';
	import { POLICY_META } from '../lib/seed';

	let meta = $derived($activeReview?.policyMeta ?? POLICY_META);

	function startNewReview() {
		goNewReview();
	}

</script>

<div class="topbar">
	<div class="tb-title">
		<span class="sb-brand-dot" style="width:24px; height:24px">
			<Icon name="grid" size={13} stroke={2.4} />
		</span>
		<span class="crumb">{$WEBUI_NAME}</span>
		<Icon name="chevR" size={12} />
		<span class="name">
			{#if $view === 'library'}
				All policies
			{:else if $stage === 'upload'}
				Policy Review
			{:else}
				{meta.name}
			{/if}
		</span>
	</div>

	<div class="tb-actions">
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
