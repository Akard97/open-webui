<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import { approvalQueue, checklistVersions, openReview } from '../lib/store';
	import { summarizeReview, versionFor } from '../lib/reviews';
	import type { Review } from '../lib/types';

	function summary(r: Review) {
		const v = versionFor(r, $checklistVersions);
		return v ? summarizeReview(r, v) : null;
	}
	function verdictTone(key: string): string {
		if (key === 'approved') return 'ok';
		if (key === 'conditional') return 'warn';
		if (key === 'rejected') return 'bad';
		return 'muted';
	}
</script>

<div class="aq-wrap">
	<header class="aq-head">
		<div class="aq-eyebrow">Policy Review</div>
		<h1>Approval queue</h1>
		<p>Reviews submitted by OE reviewers, awaiting your decision.</p>
	</header>

	{#if $approvalQueue.length === 0}
		<div class="aq-empty">
			<Icon name="check" size={22} />
			<p>No reviews awaiting approval. You're all caught up.</p>
		</div>
	{:else}
		<ul class="aq-list">
			{#each $approvalQueue as r (r.id)}
				{@const s = summary(r)}
				<li class="aq-row">
					<div class="aq-main">
						<div class="aq-title">{r.policyMeta.name}</div>
						<div class="aq-meta">
							<span class="aq-code">{r.policyMeta.code}</span>
							<span class="dot">·</span>
							<span>Reviewer: {r.createdBy}</span>
							{#if r.approval.sentAt}
								<span class="dot">·</span>
								<span>Submitted {r.approval.sentAt}</span>
							{/if}
						</div>
						{#if r.approval.note}
							<div class="aq-note">"{r.approval.note}"</div>
						{/if}
					</div>
					{#if s}
						<div class="aq-score">
							<span class="aq-num">{s.overall}%</span>
							<span class="aq-verdict {verdictTone(s.verdictKey)}">{s.verdictLabel}</span>
						</div>
					{/if}
					<button class="aq-btn" onclick={() => openReview(r.id)} type="button">
						Review <Icon name="chevR" size={13} />
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.aq-wrap { max-width: 860px; margin: 0 auto; padding: 28px 24px 40px; }
	.aq-eyebrow { font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-400); }
	.aq-head h1 { font-size: 22px; font-weight: 600; margin: 4px 0; }
	.aq-head p { color: var(--ink-500); font-size: 13px; }
	.aq-empty { text-align: center; color: var(--ink-400); padding: 70px 0; display: grid; gap: 12px; justify-items: center; }
	.aq-list { list-style: none; display: grid; gap: 10px; margin-top: 18px; }
	.aq-row { display: flex; align-items: center; gap: 16px; border: 1px solid var(--ink-100); border-radius: 12px; padding: 14px 16px; }
	.aq-main { flex: 1; min-width: 0; }
	.aq-title { font-size: 14px; font-weight: 500; }
	.aq-meta { font-size: 11.5px; color: var(--ink-400); display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-top: 3px; }
	.aq-code { font-family: var(--mono); }
	.aq-meta .dot { opacity: 0.5; }
	.aq-note { font-size: 12px; color: var(--ink-500); font-style: italic; margin-top: 6px; }
	.aq-score { text-align: right; display: grid; gap: 2px; }
	.aq-num { font-size: 16px; font-weight: 600; font-family: var(--mono); }
	.aq-verdict { font-size: 10.5px; padding: 2px 8px; border-radius: 20px; }
	.aq-verdict.ok { color: var(--ok); background: color-mix(in srgb, var(--ok) 12%, transparent); }
	.aq-verdict.warn { color: var(--warn, #b8860b); background: color-mix(in srgb, var(--warn, #b8860b) 14%, transparent); }
	.aq-verdict.bad { color: var(--bad); background: color-mix(in srgb, var(--bad) 12%, transparent); }
	.aq-verdict.muted { color: var(--ink-500); background: var(--ink-100); }
	.aq-btn { display: inline-flex; align-items: center; gap: 5px; font-size: 12.5px; padding: 8px 14px; border-radius: 9px; border: 1px solid var(--primary); background: var(--primary); color: #fff; cursor: pointer; white-space: nowrap; }
</style>
