<script lang="ts">
	// Policy Review tool's own internal sidebar. Lives between OWUI's global
	// rail (selects which tool) and the tool's main canvas. Port of
	// sidebar.jsx from the PRP-2 design handoff.
	//
	// Reads the OWUI `user` store so the avatar + role line are consistent
	// across the Hub. Falls back to design placeholders if the user store is
	// not yet hydrated (e.g. during SSR).

	import Icon from '../ui/Icon.svelte';
	import { view, resetReview, stage, canUseChecker, canApprove } from '../lib/store';
	import { user } from '$lib/stores';
	import { policyRoleLabel } from '../lib/roles';

	function go(target: 'all-policies' | 'new-review') {
		if (target === 'new-review') {
			// Starting a new review resets stage to upload + clears in-flight data.
			resetReview();
		}
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
		{#if $canUseChecker}
			<button
				class="sb-link"
				class:active={$view === 'new-review'}
				onclick={() => go('new-review')}
				type="button"
			>
				<Icon name="fileText" size={15} /> New Review
			</button>
		{/if}
		<button class="sb-link" type="button">
			<Icon name="search" size={15} /> Search policies
		</button>
	</div>

	<div class="sb-heading">Workspace</div>
	<div class="sb-section" style="padding-top: 0">
		<button class="sb-link" type="button">
			<Icon name="grid" size={15} /> Dashboard
		</button>
		<button
			class="sb-link"
			class:active={$view === 'all-policies'}
			onclick={() => go('all-policies')}
			type="button"
		>
			<Icon name="book" size={15} /> All Policies <span class="sb-count">142</span>
		</button>
		<button class="sb-link" type="button">
			<Icon name="refresh" size={15} /> In Review <span class="sb-count">7</span>
		</button>
		{#if $canApprove}
			<button class="sb-link" type="button">
				<Icon name="check" size={15} /> Approvals
				<span class="sb-count sb-count-accent">3</span>
			</button>
		{/if}
		{#if $canUseChecker}
			<button class="sb-link" type="button">
				<Icon name="shield" size={15} /> Compliance Checker
			</button>
			<button class="sb-link" type="button">
				<Icon name="alert" size={15} /> Exceptions
			</button>
		{/if}
	</div>

	<div class="sb-foot-links">
		<button class="sb-link" type="button"><Icon name="folder" size={15} /> Templates</button>
		<button class="sb-link" type="button"><Icon name="clock" size={15} /> Audit log</button>
		<button class="sb-link" type="button"><Icon name="sliders" size={15} /> Settings</button>
	</div>

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
	/* Make sb-link buttons match the design's div-based version. */
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
