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

	const recent = [
		{ ico: '📘', label: 'Digital City Asset Disposal', meta: 'In Review', active: true },
		{ ico: '📘', label: 'Ishbilia Compound Valuation', meta: 'Approved' },
		{ ico: '📘', label: 'Selling Digital City Assets', meta: 'Approved' },
		{ ico: '📘', label: 'Abraj Altawiniah Information', meta: 'Draft' },
		{ ico: '📘', label: 'Osool Disposal & Valuation', meta: 'Approved' },
		{ ico: '📘', label: 'Digital City Disposal Process', meta: 'Rejected' }
	];

	const archived = [
		{ ico: '📕', label: 'FY24 Procurement Policy', meta: 'Q4' },
		{ ico: '📕', label: 'Vendor Onboarding v3', meta: 'Q3' },
		{ ico: '📕', label: 'Capital Allocation Framework', meta: 'Q3' }
	];

	function pillClass(meta: string): string {
		return `pill-${meta.toLowerCase().replace(/\s/g, '')}`;
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

	<div class="sb-heading">Recent reviews</div>
	<div class="sb-chats">
		{#each recent as c, i (i)}
			<div class="sb-chat" class:active={c.active}>
				<span class="ico">{c.ico}</span>
				<span class="label">{c.label}</span>
				<span class="pill {pillClass(c.meta)}">{c.meta}</span>
			</div>
		{/each}

		<div class="sb-heading" style="padding-left: 8px">Archived</div>
		{#each archived as c, i (`a${i}`)}
			<div class="sb-chat">
				<span class="ico">{c.ico}</span>
				<span class="label">{c.label}</span>
				<span class="meta">{c.meta}</span>
			</div>
		{/each}
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
				Organizational Excellence{$canApprove ? ' · Approver' : $canUseChecker ? ' · Reviewer' : ''}
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
