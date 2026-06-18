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
	let openMineAll = $derived(
		$myReviews.filter((r) => r.status === 'draft' || r.status === 'rejected')
	);
	let openMine = $derived(openMineAll.slice(0, 4));
	let pending = $derived($approvalQueue.slice(0, 4));
	// POLICIES is static seed data; make `recent`/`publishedCount` $derived if this is wired to a live store.
	const recent = recentlyUpdated(
		POLICIES.filter((p) => p.status === 'approved'),
		4,
		60
	);
	const publishedCount = POLICIES.filter((p) => p.status === 'approved').length;

	// Header stats band — each stat is permission-gated and derived from the
	// same stores that gate the cards below; no new data is introduced.
	let stats = $derived(
		[
			$canUseChecker ? { v: openMineAll.length, l: 'in progress' } : null,
			$canApprove ? { v: $approvalQueue.length, l: 'awaiting you' } : null,
			{ v: publishedCount, l: 'published' }
		].filter((s): s is { v: number; l: string } => s !== null)
	);

	// Function color tokens, mirroring the .pl-fn-* swatches in styles.css.
	// Applied inline to the published-card accent bar so it matches the
	// Library page without relying on global/scoped CSS specificity.
	const FN_COLOR: Record<string, string> = {
		FIN: 'oklch(0.55 0.13 265)',
		HR: 'oklch(0.50 0.12 155)',
		IT: 'oklch(0.55 0.12 195)',
		RM: 'oklch(0.55 0.16 25)',
		GOV: 'oklch(0.55 0.13 310)',
		LEG: 'oklch(0.60 0.13 75)',
		RE: 'oklch(0.55 0.10 220)',
		PROC: 'oklch(0.60 0.13 55)',
		HSE: 'oklch(0.55 0.12 135)',
		OPS: 'oklch(0.55 0.08 240)'
	};
	const fnColor = (fn: string) => FN_COLOR[fn.toUpperCase()] ?? 'var(--ink-300)';

	function scoreOf(r: Review): number {
		const v = versionFor(r, $checklistVersions);
		return v ? summarizeReview(r, v).overall : 0;
	}
</script>

<div class="ov-page">
	<div class="ov-brandline"></div>
	<div class="ov-wrap">
		<header class="ov-head">
			<div class="ov-eyebrow">
				<span class="em">Policy Review</span><span class="d" aria-hidden="true"></span>Dashboard
			</div>
			<h1>Welcome back, {firstName}</h1>
			<p>Review policies against the PRP Master Checklist and publish approved policies to the library.</p>
			{#if stats.length}
				<div class="ov-stats">
					{#each stats as s, i (s.l)}
						{#if i > 0}<span class="ov-stats-sep">·</span>{/if}
						<div class="ov-stat {i === 0 ? 'lead' : ''}"><b>{s.v}</b><span>{s.l}</span></div>
					{/each}
				</div>
			{/if}
		</header>

		<div class="ov-grid">
			<div class="ov-row-cards">
				{#if $canUseChecker}
					<section class="ov-card">
						<div class="ov-card-h">
							<h2><span class="ov-dot teal"></span>My reviews</h2>
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
							<h2><span class="ov-dot olive"></span>Awaiting your approval</h2>
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
			</div>

			<section class="ov-card">
				<div class="ov-card-h">
					<h2><span class="ov-dot deep"></span>Recently published</h2>
					<button class="ov-link" onclick={() => view.set('library')} type="button">
						Browse library <Icon name="chevR" size={12} />
					</button>
				</div>
				<div class="ov-recent">
					{#each recent as p (p.code)}
						<button class="ov-rc" onclick={() => view.set('library')} type="button">
							<span class="accent" style="background: {fnColor(p.fn)}"></span>
							<div class="ov-rc-fn">{FN_META[p.fn]?.name ?? p.fn}</div>
							<div class="ov-rc-title">{p.title}</div>
							<div class="ov-rc-code">{p.code}</div>
						</button>
					{/each}
				</div>
			</section>
		</div>
	</div>
</div>

<style>
	.ov-page { min-height: 100%; }
	.ov-brandline { height: 2px; background: linear-gradient(90deg, #003B4A 0%, #0F5567 35%, #769A4A 100%); }
	.ov-wrap { max-width: 920px; margin: 0 auto; padding: 28px 24px 40px; }

	.ov-eyebrow { font-family: var(--mono); font-size: 10px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--ink-500); display: flex; align-items: center; gap: 8px; }
	.ov-eyebrow .em { color: var(--primary); font-weight: 600; }
	.ov-eyebrow .d { width: 3px; height: 3px; border-radius: 50%; background: var(--ink-300); }
	.ov-head h1 { font-size: 25px; font-weight: 600; letter-spacing: -0.02em; margin: 10px 0 4px; }
	.ov-head p { color: var(--ink-500); font-size: 13.5px; max-width: 60ch; }

	.ov-stats { display: flex; align-items: baseline; gap: 16px; margin-top: 16px; padding-top: 15px; border-top: 1px solid var(--ink-100); flex-wrap: wrap; }
	.ov-stat { display: flex; align-items: baseline; gap: 7px; }
	.ov-stat b { font-size: 21px; font-weight: 600; color: var(--ink-900); font-variant-numeric: tabular-nums; }
	.ov-stat.lead b { color: var(--primary); }
	.ov-stat span { font-size: 10.5px; color: var(--ink-500); text-transform: uppercase; letter-spacing: 0.07em; }
	.ov-stats-sep { color: var(--ink-200); }

	.ov-grid { display: grid; gap: 16px; margin-top: 22px; }
	.ov-row-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }

	.ov-card { border: 1px solid var(--ink-100); border-radius: 14px; padding: 16px 18px; background: var(--surface, #fff); transition: border-color .18s, box-shadow .18s, transform .18s; }
	.ov-card:hover { border-color: var(--ink-200); box-shadow: var(--shadow-md); }
	.ov-card-h { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
	.ov-card-h h2 { font-size: 14px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
	.ov-dot { width: 7px; height: 7px; border-radius: 2px; flex-shrink: 0; }
	.ov-dot.teal { background: var(--primary); }
	.ov-dot.olive { background: #769A4A; }
	.ov-dot.deep { background: var(--primary-500); }
	.ov-badge { font-size: 12px; font-weight: 600; color: var(--primary); background: var(--primary-50); padding: 2px 9px; border-radius: 20px; }
	.ov-empty { color: var(--ink-400); font-size: 13px; padding: 6px 0; }
	.ov-list { list-style: none; display: grid; gap: 6px; }
	.ov-row { display: flex; align-items: center; gap: 10px; width: 100%; text-align: left; background: none; border: 0; padding: 8px 10px; border-radius: 9px; cursor: pointer; transition: background .12s; }
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
	.ov-rc { position: relative; text-align: left; border: 1px solid var(--ink-100); border-radius: 11px; padding: 16px 12px 11px; background: none; cursor: pointer; overflow: hidden; transition: border-color .18s, box-shadow .18s, transform .18s; }
	.ov-rc:hover { border-color: var(--ink-200); box-shadow: var(--shadow-md); transform: translateY(-1px); }
	.ov-rc .accent { position: absolute; top: 0; left: 0; right: 0; height: 2px; }
	.ov-rc-fn { font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-400); }
	.ov-rc-title { font-size: 13px; font-weight: 500; margin: 3px 0; color: var(--ink-900); }
	.ov-rc-code { font-size: 11px; font-family: var(--mono); color: var(--ink-400); }
</style>
