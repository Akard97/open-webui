<script lang="ts">
	// Lean, role-aware tool sidebar. Every visible item routes to a working view.
	// The Admin entry is intentionally absent — it ships with the admin page (Plan 3).

	import Icon from '../ui/Icon.svelte';
	import {
		view,
		canUseChecker,
		canApprove,
		myReviews,
		approvalQueue,
		goNewReview
	} from '../lib/store';
	import { user } from '$lib/stores';
	import { policyRoleLabel } from '../lib/roles';

	function go(target: 'overview' | 'library' | 'my-reviews' | 'approvals') {
		view.set(target);
	}

	function initials(name: string | undefined): string {
		if (!name) return 'A';
		return name
			.split(/\s+/)
			.slice(0, 2)
			.map((w) => w[0])
			.join('')
			.toUpperCase();
	}
</script>

<aside class="sidebar">
	<div class="sb-top">
		<div class="sb-brand">
			<div class="sb-brand-dot"><Icon name="shield" size={12} stroke={2.2} /></div>
			Policy Review
		</div>
		<button class="sb-icon-btn" title="Collapse" type="button">
			<Icon name="sidebar" size={16} />
		</button>
	</div>

	<div class="sb-section">
		<button class="sb-link" class:active={$view === 'overview'} onclick={() => go('overview')} type="button">
			<Icon name="grid" size={15} /> Overview
		</button>
		<button class="sb-link" class:active={$view === 'library'} onclick={() => go('library')} type="button">
			<Icon name="book" size={15} /> Policy library
		</button>
	</div>

	{#if $canUseChecker}
		<div class="sb-heading">Reviewing</div>
		<div class="sb-section" style="padding-top: 0">
			<button
				class="sb-link"
				class:active={$view === 'new-review'}
				onclick={goNewReview}
				type="button"
			>
				<Icon name="fileText" size={15} /> New review
			</button>
			<button
				class="sb-link"
				class:active={$view === 'my-reviews'}
				onclick={() => go('my-reviews')}
				type="button"
			>
				<Icon name="refresh" size={15} /> My reviews
				{#if $myReviews.length}<span class="sb-count">{$myReviews.length}</span>{/if}
			</button>
		</div>
	{/if}

	{#if $canApprove}
		<div class="sb-heading">Approvals</div>
		<div class="sb-section" style="padding-top: 0">
			<button
				class="sb-link"
				class:active={$view === 'approvals'}
				onclick={() => go('approvals')}
				type="button"
			>
				<Icon name="check" size={15} /> Approval queue
				{#if $approvalQueue.length}<span class="sb-count sb-count-accent">{$approvalQueue.length}</span>{/if}
			</button>
		</div>
	{/if}

	<div class="sb-bottom">
		{#if $user?.profile_image_url}
			<img class="avatar" src={$user.profile_image_url} alt={$user?.name ?? ''} />
		{:else}
			<div class="avatar">{initials($user?.name)}</div>
		{/if}
		<div style="display:flex; flex-direction:column; line-height:1.2">
			<span style="font-size:13px; font-weight:500">{$user?.name ?? 'Ahmad'}</span>
			<span style="font-size:11px; color:var(--ink-400)">
				{policyRoleLabel($canApprove, $canUseChecker)}
			</span>
		</div>
	</div>
</aside>

<style>
	.sb-link {
		background: none;
		border: 0;
		width: 100%;
		text-align: left;
	}
	.sb-bottom .avatar {
		object-fit: cover;
	}
</style>
