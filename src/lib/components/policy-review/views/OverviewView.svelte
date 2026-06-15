<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import {
		canUseChecker,
		canApprove,
		myReviews,
		approvalQueue,
		checklistVersions,
		view,
		openReview,
		goNewReview
	} from '../lib/store';
	import { POLICIES, FN_META } from '../lib/seed';
	import { recentlyUpdated } from '../lib/library';
	import { summarizeReview, versionFor, REVIEW_STATUS_META } from '../lib/reviews';
	import { user } from '$lib/stores';
	import type { Review } from '../lib/types';

	let firstName = $derived(($user?.name ?? 'there').split(/\s+/)[0]);
	let openMine = $derived(
		$myReviews.filter((r) => r.status === 'draft' || r.status === 'rejected').slice(0, 4)
	);
	let pending = $derived($approvalQueue.slice(0, 4));
	const recent = recentlyUpdated(
		POLICIES.filter((p) => p.status === 'approved'),
		4,
		60
	);

	function scoreOf(r: Review): number {
		const v = versionFor(r, $checklistVersions);
		return v ? summarizeReview(r, v).overall : 0;
	}
</script>

<div class="ov-wrap">
	<header class="ov-head">
		<div class="ov-eyebrow">Policy Review</div>
		<h1>Welcome back, {firstName}</h1>
		<p>Review policies against the PRP Master Checklist and publish approved policies to the library.</p>
	</header>

	<div class="ov-grid">
		{#if $canUseChecker}
			<section class="ov-card">
				<div class="ov-card-h">
					<h2>My reviews</h2>
					<button class="ov-btn primary" onclick={goNewReview} type="button">
						<Icon name="fileText" size={13} /> New review
					</button>
				</div>
				{#if openMine.length === 0}
					<p class="ov-empty">No reviews in progress. Start one with "New review".</p>
				{:else}
					<ul class="ov-list">
						{#each openMine as r (r.id)}
							<li>
								<button class="ov-row" onclick={() => openReview(r.id)} type="button">
									<span class="ov-row-title">{r.policyMeta.name}</span>
									<span class="ov-chip {REVIEW_STATUS_META[r.status].tone}">{REVIEW_STATUS_META[r.status].label}</span>
									<span class="ov-row-score">{scoreOf(r)}%</span>
								</button>
							</li>
						{/each}
					</ul>
					<button class="ov-link" onclick={() => view.set('my-reviews')} type="button">
						View all my reviews <Icon name="chevR" size={12} />
					</button>
				{/if}
			</section>
		{/if}

		{#if $canApprove}
			<section class="ov-card">
				<div class="ov-card-h">
					<h2>Awaiting your approval</h2>
					{#if $approvalQueue.length}<span class="ov-badge">{$approvalQueue.length}</span>{/if}
				</div>
				{#if pending.length === 0}
					<p class="ov-empty">Nothing in the queue. You're all caught up.</p>
				{:else}
					<ul class="ov-list">
						{#each pending as r (r.id)}
							<li>
								<button class="ov-row" onclick={() => openReview(r.id)} type="button">
									<span class="ov-row-title">{r.policyMeta.name}</span>
									<span class="ov-row-sub">{r.createdBy}</span>
									<span class="ov-row-score">{scoreOf(r)}%</span>
								</button>
							</li>
						{/each}
					</ul>
					<button class="ov-link" onclick={() => view.set('approvals')} type="button">
						Open approval queue <Icon name="chevR" size={12} />
					</button>
				{/if}
			</section>
		{/if}

		<section class="ov-card">
			<div class="ov-card-h">
				<h2>Recently published</h2>
				<button class="ov-link" onclick={() => view.set('library')} type="button">
					Browse library <Icon name="chevR" size={12} />
				</button>
			</div>
			<div class="ov-recent">
				{#each recent as p (p.code)}
					<button class="ov-rc" onclick={() => view.set('library')} type="button">
						<div class="ov-rc-fn">{FN_META[p.fn]?.name ?? p.fn}</div>
						<div class="ov-rc-title">{p.title}</div>
						<div class="ov-rc-code">{p.code}</div>
					</button>
				{/each}
			</div>
		</section>
	</div>
</div>

<style>
	.ov-wrap { max-width: 920px; margin: 0 auto; padding: 28px 24px 40px; }
	.ov-eyebrow { font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-400); }
	.ov-head h1 { font-size: 24px; font-weight: 600; margin: 6px 0 4px; }
	.ov-head p { color: var(--ink-500); font-size: 13.5px; max-width: 60ch; }
	.ov-grid { display: grid; gap: 16px; margin-top: 22px; }
	.ov-card { border: 1px solid var(--ink-100); border-radius: 14px; padding: 16px 18px; background: var(--surface, #fff); }
	.ov-card-h { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
	.ov-card-h h2 { font-size: 14px; font-weight: 600; }
	.ov-badge { font-size: 12px; font-weight: 600; color: var(--primary); background: var(--primary-50); padding: 2px 9px; border-radius: 20px; }
	.ov-empty { color: var(--ink-400); font-size: 13px; padding: 6px 0; }
	.ov-list { list-style: none; display: grid; gap: 6px; }
	.ov-row { display: flex; align-items: center; gap: 10px; width: 100%; text-align: left; background: none; border: 0; padding: 8px 10px; border-radius: 9px; cursor: pointer; }
	.ov-row:hover { background: var(--ink-50, rgba(0,0,0,0.03)); }
	.ov-row-title { flex: 1; min-width: 0; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.ov-row-sub { font-size: 11.5px; color: var(--ink-400); }
	.ov-row-score { font-size: 12px; font-family: var(--mono); color: var(--ink-500); }
	.ov-chip { font-size: 10.5px; padding: 2px 8px; border-radius: 20px; }
	.ov-chip.ok { color: var(--ok); background: color-mix(in srgb, var(--ok) 12%, transparent); }
	.ov-chip.bad { color: var(--bad); background: color-mix(in srgb, var(--bad) 12%, transparent); }
	.ov-chip.info { color: var(--primary); background: var(--primary-50); }
	.ov-chip.muted { color: var(--ink-500); background: var(--ink-100); }
	.ov-link { background: none; border: 0; color: var(--primary); font-size: 12.5px; cursor: pointer; display: inline-flex; align-items: center; gap: 3px; padding: 4px 0; }
	.ov-btn { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; padding: 6px 12px; border-radius: 9px; border: 1px solid var(--ink-200); background: none; cursor: pointer; }
	.ov-btn.primary { background: var(--primary); color: #fff; border-color: var(--primary); }
	.ov-recent { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; }
	.ov-rc { text-align: left; border: 1px solid var(--ink-100); border-radius: 11px; padding: 11px 12px; background: none; cursor: pointer; }
	.ov-rc:hover { border-color: var(--ink-200); }
	.ov-rc-fn { font-size: 10.5px; color: var(--ink-400); text-transform: uppercase; letter-spacing: 0.04em; }
	.ov-rc-title { font-size: 13px; font-weight: 500; margin: 3px 0; }
	.ov-rc-code { font-size: 11px; font-family: var(--mono); color: var(--ink-400); }
</style>
