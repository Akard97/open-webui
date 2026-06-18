<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import { myReviews, checklistVersions, openReview, goNewReview, deleteReview } from '../lib/store';
	import { summarizeReview, versionFor, REVIEW_STATUS_META } from '../lib/reviews';
	import type { Review } from '../lib/types';

	// Active work first (draft / returned), then pending, then decided.
	const ORDER: Record<Review['status'], number> = { rejected: 0, draft: 1, pending: 2, approved: 3 };
	let rows = $derived(
		[...$myReviews].sort((a, b) => ORDER[a.status] - ORDER[b.status])
	);

	// Only a draft or returned (rejected) review can be deleted by its owner; the
	// backend enforces this too. Two-click confirm avoids a native confirm() dialog.
	let confirmingId = $state<string | null>(null);
	const deletable = (r: Review) => r.status === 'draft' || r.status === 'rejected';

	async function onDelete(r: Review) {
		if (confirmingId !== r.id) {
			confirmingId = r.id; // arm — a second click confirms
			return;
		}
		await deleteReview(r.id);
		confirmingId = null;
	}

	function scoreOf(r: Review): number {
		const v = versionFor(r, $checklistVersions);
		return v ? summarizeReview(r, v).overall : 0;
	}
</script>

<div class="mr-wrap">
	<header class="mr-head">
		<div>
			<div class="mr-eyebrow">Policy Review</div>
			<h1>My reviews</h1>
		</div>
		<button class="mr-btn primary" onclick={goNewReview} type="button">
			<Icon name="fileText" size={13} /> New review
		</button>
	</header>

	{#if rows.length === 0}
		<div class="mr-empty">
			<p>You haven't started any reviews yet.</p>
			<button class="mr-btn primary" onclick={goNewReview} type="button">
				<Icon name="fileText" size={13} /> Start your first review
			</button>
		</div>
	{:else}
		<ul class="mr-list">
			{#each rows as r (r.id)}
				<li class="mr-item">
					<button class="mr-row" onclick={() => openReview(r.id)} type="button">
						<div class="mr-main">
							<div class="mr-title">{r.policyMeta.name}</div>
							<div class="mr-meta">
								<span class="mr-code">{r.policyMeta.code}</span>
								<span class="dot">·</span>
								<span>{r.policyMeta.version}</span>
								<span class="dot">·</span>
								<span>Created {r.createdAt}</span>
							</div>
						</div>
						<span class="mr-chip {REVIEW_STATUS_META[r.status].tone}">
							{REVIEW_STATUS_META[r.status].label}
						</span>
						<span class="mr-score">{scoreOf(r)}%</span>
						<Icon name="chevR" size={15} />
					</button>
					{#if deletable(r)}
						<button
							class="mr-del"
							class:confirming={confirmingId === r.id}
							onclick={() => onDelete(r)}
							onmouseleave={() => { if (confirmingId === r.id) confirmingId = null; }}
							type="button"
							aria-label="Delete {r.policyMeta.name}"
							title={confirmingId === r.id ? 'Click again to confirm' : 'Delete review'}
						>
							{#if confirmingId === r.id}Confirm{:else}<Icon name="trash" size={15} />{/if}
						</button>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.mr-wrap { max-width: 860px; margin: 0 auto; padding: 28px 24px 40px; }
	.mr-head { display: flex; align-items: flex-end; justify-content: space-between; margin-bottom: 18px; }
	.mr-eyebrow { font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-400); }
	.mr-head h1 { font-size: 22px; font-weight: 600; margin-top: 4px; }
	.mr-btn { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; padding: 7px 13px; border-radius: 9px; border: 1px solid var(--ink-200); background: none; cursor: pointer; }
	.mr-btn.primary { background: var(--primary); color: #fff; border-color: var(--primary); }
	.mr-empty { text-align: center; color: var(--ink-500); padding: 60px 0; display: grid; gap: 14px; justify-items: center; }
	.mr-list { list-style: none; display: grid; gap: 8px; }
	.mr-item { display: flex; align-items: stretch; gap: 8px; }
	.mr-item .mr-row { flex: 1; min-width: 0; }
	.mr-row { display: flex; align-items: center; gap: 14px; width: 100%; text-align: left; background: none; border: 1px solid var(--ink-100); border-radius: 12px; padding: 13px 15px; cursor: pointer; color: inherit; }
	.mr-row:hover { border-color: var(--ink-200); }
	.mr-del { display: inline-flex; align-items: center; justify-content: center; padding: 0 13px; border: 1px solid var(--ink-100); border-radius: 12px; background: none; color: var(--ink-400); cursor: pointer; font-size: 12px; white-space: nowrap; }
	.mr-del:hover { color: var(--bad); border-color: color-mix(in srgb, var(--bad) 40%, var(--ink-200)); }
	.mr-del.confirming { color: #fff; background: var(--bad); border-color: var(--bad); font-weight: 600; }
	.mr-main { flex: 1; min-width: 0; }
	.mr-title { font-size: 14px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.mr-meta { font-size: 11.5px; color: var(--ink-400); display: flex; gap: 6px; align-items: center; margin-top: 3px; }
	.mr-code { font-family: var(--mono); }
	.mr-meta .dot { opacity: 0.5; }
	.mr-score { font-size: 13px; font-family: var(--mono); color: var(--ink-500); min-width: 38px; text-align: right; }
	.mr-chip { font-size: 11px; padding: 3px 10px; border-radius: 20px; white-space: nowrap; }
	.mr-chip.ok { color: var(--ok); background: color-mix(in srgb, var(--ok) 12%, transparent); }
	.mr-chip.bad { color: var(--bad); background: color-mix(in srgb, var(--bad) 12%, transparent); }
	.mr-chip.info { color: var(--primary); background: var(--primary-50); }
	.mr-chip.muted { color: var(--ink-500); background: var(--ink-100); }
</style>
