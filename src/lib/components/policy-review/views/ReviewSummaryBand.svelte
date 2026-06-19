<script lang="ts">
	// Overview band — state-adaptive summary + decision header for the review page.
	// Absorbs the old right rail (Decision / Score by Theme / Strengths / Gaps) and
	// the old ApprovalBanner (pending / approved / rejected status + approve/reject).
	import Icon from '../ui/Icon.svelte';
	import VerdictBadge from '../ui/VerdictBadge.svelte';
	import { computeScores } from '../lib/scoring';
	import {
		resolveMode,
		countResults,
		openCount as openCountOf,
		resolvedCount,
		topGaps
	} from '../lib/reviewView';
	import {
		activeReview,
		activeVersion,
		canUseChecker,
		canApprove,
		submitModalOpen,
		replaceDocument,
		approveAndPublish,
		rejectPolicy
	} from '../lib/store';
	import { reviewDocumentUrl } from '../lib/api';
	import type { Verdict } from '../lib/types';

	let { onPickGap }: { onPickGap: (sectionId: string, n: number) => void } = $props();

	let review = $derived($activeReview);
	let version = $derived($activeVersion);
	let results = $derived(review?.results ?? {});
	let meta = $derived(review?.policyMeta);
	let approval = $derived(review?.approval ?? null);
	let strengths = $derived(review?.strengths ?? []);
	let scoreResult = $derived(version ? computeScores(version, results) : null);
	let counts = $derived(
		version
			? countResults(version, results)
			: { compliant: 0, 'non-compliant': 0, human: 0, pending: 0, total: 0 }
	);
	let gaps = $derived(version ? topGaps(version, results) : []);
	let mode = $derived(review ? resolveMode(review.status, $canUseChecker, $canApprove) : 'readonly');
	let document_ = $derived(review?.policyMeta?.document ?? null);
	let canReplace = $derived(
		$canUseChecker && review != null && (review.status === 'draft' || review.status === 'rejected')
	);
	let openItems = $derived(openCountOf(counts));
	let resolved = $derived(resolvedCount(counts));
	let threshold = $derived(version?.verdictBands?.approved ?? 85);

	// Once approved/rejected, the RECORDED decision is the headline — not a live recompute.
	let recordedVerdict = $derived<Verdict | null>(
		review?.status === 'approved'
			? { key: 'approved', label: 'Approved', reason: '' }
			: review?.status === 'rejected'
				? { key: 'rejected', label: 'Rejected', reason: '' }
				: null
	);

	// ── Replace document (reviewer mode) ──
	let replaceInput = $state<HTMLInputElement | undefined>(undefined);
	let replacing = $state(false);
	async function onReplaceChange(e: Event) {
		const f = (e.target as HTMLInputElement).files?.[0];
		if (!f || !review) return;
		replacing = true;
		try {
			await replaceDocument(review.id, f);
		} finally {
			replacing = false;
			if (replaceInput) replaceInput.value = '';
		}
	}

	// ── Approve / reject (decide mode) ──
	let approvalError = $state('');
	let approving = $state(false);
	let rejectOpen = $state(false);
	let rejectNote = $state('');
	async function approve() {
		if (!review || approving) return;
		approving = true;
		approvalError = '';
		try {
			await approveAndPublish(review.id);
		} catch (e) {
			approvalError = String(e);
		} finally {
			approving = false;
		}
	}
	function openReject() {
		approvalError = '';
		rejectOpen = true;
	}
	function cancelReject() {
		rejectOpen = false;
		rejectNote = '';
		approvalError = '';
	}
	async function confirmReject() {
		if (!review || !rejectNote.trim()) return;
		approvalError = '';
		try {
			await rejectPolicy(review.id, rejectNote.trim());
			rejectOpen = false;
			rejectNote = '';
		} catch (e) {
			approvalError = String(e);
		}
	}

	function openSubmit() {
		submitModalOpen.set(true);
	}

	// Read-only status line for pending-creator / approved / rejected-viewer.
	let statusText = $derived.by(() => {
		if (!approval) return '';
		if (approval.status === 'pending')
			return `Submitted for approval — awaiting OE approver${approval.sentAt ? ` · ${approval.sentAt}` : ''}`;
		if (approval.status === 'approved')
			return `Approved & published${approval.decidedBy ? ` by ${approval.decidedBy}` : ''}${approval.decidedAt ? ` · ${approval.decidedAt}` : ''}`;
		if (approval.status === 'rejected')
			return `Rejected${approval.decidedBy ? ` by ${approval.decidedBy}` : ''}${approval.decidedAt ? ` · ${approval.decidedAt}` : ''}`;
		return '';
	});
</script>

{#if review && version && scoreResult && meta}
	<section class="rv-band" aria-label="Review summary">
		<!-- Identity row -->
		<div class="rv-identity">
			<div style="min-width:0; flex:1">
				<div class="rv-eyebrow">Policy review</div>
				<h1 class="rv-title">{meta.name}</h1>
				<div class="rv-meta">
					<span>{meta.code}</span><span class="sep">·</span>
					<span>{meta.version}</span><span class="sep">·</span>
					<span>{meta.pages} pages</span><span class="sep">·</span>
					<span>Reviewed {meta.reviewDate}</span><span class="sep">·</span>
					<span>Reviewer: {meta.reviewer}</span>
				</div>
				{#if document_}
					<div class="rv-source">
						<a class="src-link" href={reviewDocumentUrl(review.id)} target="_blank" rel="noopener">
							<Icon name="fileText" size={13} />
							{document_.filename}
							<span class="src-dl">Download</span>
						</a>
						{#if canReplace}
							<button class="src-replace" type="button" onclick={() => replaceInput?.click()} disabled={replacing}>
								{replacing ? 'Replacing…' : 'Replace'}
							</button>
							<input bind:this={replaceInput} type="file" accept=".pdf,.docx,.md,.txt" style="display:none" onchange={onReplaceChange} />
						{/if}
					</div>
				{/if}
			</div>
		</div>

		<!-- Decision cluster -->
		<div class="rv-decision">
			<div class="rv-stat">
				<span class="rv-stat-l">Verdict</span>
				{#if recordedVerdict}
					<VerdictBadge verdict={recordedVerdict} />
				{:else}
					<VerdictBadge verdict={scoreResult.verdict} />
				{/if}
			</div>
			<div class="rv-stat">
				<span class="rv-stat-l">Weighted score</span>
				<span class="rv-score">{scoreResult.overall}<span class="pct">%</span></span>
			</div>
			<div class="rv-stat">
				<span class="rv-stat-l">Mandatory gates</span>
				<span class="rv-stat-v" style="color:{scoreResult.gatesPass ? 'var(--ok)' : 'var(--bad)'}">
					{scoreResult.gatesPass ? 'Both pass' : 'Not passing'}
				</span>
			</div>
			<div class="rv-stat">
				<span class="rv-stat-l">Threshold for issue</span>
				<span class="rv-stat-v">≥ {threshold}%</span>
			</div>
			{#if mode === 'reviewer'}
				<div class="rv-stat">
					<span class="rv-stat-l">Progress</span>
					<span class="rv-stat-v">{resolved}/{counts.total}</span>
				</div>
				<div class="rv-stat">
					<span class="rv-stat-l">Open items</span>
					<span class="rv-stat-v" style="color:{openItems ? 'var(--warn)' : 'var(--ink-700)'}">
						{openItems}{counts.human ? ` · ${counts.human} human` : ''}
					</span>
				</div>
			{:else}
				{#if mode === 'decide' && approval?.sentAt}
					<div class="rv-stat">
						<span class="rv-stat-l">Submitted</span>
						<span class="rv-stat-v">{approval.sentAt}</span>
					</div>
				{/if}
				<div class="rv-stat">
					<span class="rv-stat-l">Items pending human</span>
					<span class="rv-stat-v">{counts.human}</span>
				</div>
			{/if}

			<!-- Action zone -->
			<div class="rv-action">
				{#if mode === 'reviewer'}
					<button
						class="btn btn-primary"
						type="button"
						onclick={openSubmit}
						disabled={scoreResult.humanItemsRemain || approval?.status === 'pending'}
					>
						<Icon name="send" size={13} />
						{approval?.status === 'pending' ? 'Submitted for approval' : 'Submit for Approval'}
					</button>
					{#if openItems > 0}
						<div class="rv-hint">Resolve {openItems} open item{openItems === 1 ? '' : 's'} before submitting</div>
					{/if}
				{:else if mode === 'decide'}
					{#if approval?.status === 'pending'}
						<div class="rv-decide-actions">
							<button class="btn btn-primary" type="button" onclick={approve} disabled={approving}>Approve &amp; Publish</button>
							{#if !rejectOpen}
								<button class="btn" type="button" onclick={openReject}>Reject</button>
							{/if}
						</div>
					{/if}
				{:else}
					<div class="rv-status {approval?.status ?? 'idle'}">{statusText}</div>
				{/if}
			</div>
		</div>

		<!-- Rejection note (visible to the reviewer working a rejected review) -->
		{#if approval?.note && approval.status === 'rejected'}
			<div class="rv-reject-note">"{approval.note}"</div>
		{/if}

		<!-- Reject form (decide mode) -->
		{#if mode === 'decide' && rejectOpen}
			<div class="editor-grid rv-reject-form">
				<div>
					<label for="reject-note">Rejection note (required)</label>
					<textarea id="reject-note" bind:value={rejectNote} placeholder="Explain what the reviewer needs to change before resubmitting…"></textarea>
				</div>
				<div class="rv-reject-buttons">
					<button class="btn btn-sm" type="button" onclick={cancelReject}>Cancel</button>
					<button class="btn btn-sm btn-danger" type="button" onclick={confirmReject} disabled={!rejectNote.trim()}>Confirm rejection</button>
				</div>
			</div>
		{/if}
		{#if approvalError}
			<div class="rv-error">{approvalError}</div>
		{/if}

		<!-- Score by theme -->
		<div class="rv-theme-grid">
			{#each scoreResult.themeRows as t (t.id)}
				{@const isFail = t.gate && t.pct < t.threshold && t.total > 0}
				{@const isWarn = t.pct < 70 && !isFail && t.total > 0}
				{@const cls = isFail ? 'fail' : isWarn ? 'warn' : ''}
				<div class="rv-theme">
					<div class="theme-score-row">
						<span class="id">{t.id}</span>
						<span class="name">
							<span class="nm">{t.name}</span>
							{#if t.gate}<span class="gate-mini">GATE</span>{/if}
						</span>
						<span class="val {cls}">{t.pct}%</span>
					</div>
					<div class="theme-score-bar"><div class="fill {cls}" style="width:{t.pct}%"></div></div>
				</div>
			{/each}
		</div>

		<!-- Strengths + critical gaps -->
		<div class="rv-split">
			<div>
				<h4 class="rv-h">Top strengths</h4>
				<div class="gap-list">
					{#each strengths as s (s)}
						<div class="gap-item strength"><span class="n">+</span><span>{s}</span></div>
					{/each}
					{#if strengths.length === 0}
						<div class="rv-empty">No strengths recorded.</div>
					{/if}
				</div>
			</div>
			<div>
				<h4 class="rv-h">Critical gaps — must be resolved</h4>
				{#if gaps.length === 0}
					<div class="rv-empty">No critical gaps remain.</div>
				{:else}
					<div class="gap-list">
						{#each gaps as g, i (g.ref)}
							<button class="gap-item rv-gap" type="button" onclick={() => onPickGap(g.sectionId, g.n)}>
								<span class="n">{i + 1}</span>
								<div>
									<div class="rv-gap-title">{g.title}</div>
									<div class="rv-gap-ref">{g.ref} · {g.theme}</div>
								</div>
							</button>
						{/each}
					</div>
				{/if}
			</div>
		</div>
	</section>
{/if}
