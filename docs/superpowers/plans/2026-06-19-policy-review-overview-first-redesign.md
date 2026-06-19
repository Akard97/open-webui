# Policy Review overview-first redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the Policy Review detail page into an overview-first layout — a state-adaptive summary band on top, with a collapsed-by-default Theme → PRP Group → Item checklist below — without losing any current capability.

**Architecture:** Extract the page's pure presentation logic (mode resolution, counts, gaps, item numbering, collapse-default map) into a unit-tested module. Move the old right rail and the old approval banner into one new `ReviewSummaryBand.svelte`. Rewrite `ReviewView.svelte` as a single scrolling column (brand line → band → filters → three-tier collapsible checklist). Replace the rail/layout CSS in `styles.css` with band + single-column styles plus responsive/RTL/contrast/focus fixes. Harden `ItemDrawer.svelte` for accessibility. All styles stay inside `@scope (.pr-root)`.

**Tech Stack:** SvelteKit + Svelte 5 runes (`$state`/`$derived`/`$props`/`$effect`), TypeScript, plain CSS (`styles.css`), Vitest for unit tests, svelte-check + eslint for static checks. Spec: [docs/superpowers/specs/2026-06-19-policy-review-overview-first-redesign-design.md](../specs/2026-06-19-policy-review-overview-first-redesign-design.md).

---

## File structure

- **Create** `src/lib/components/policy-review/lib/reviewView.ts` — pure helpers: `resolveMode`, `isLocked`, `countResults`, `openCount`, `resolvedCount`, `itemNumber`, `topGaps`, `initOpenMap`. No SvelteKit/`$app`/`$lib` imports, so it unit-tests cleanly.
- **Create** `src/lib/components/policy-review/lib/reviewView.test.ts` — Vitest coverage for the above.
- **Create** `src/lib/components/policy-review/views/ReviewSummaryBand.svelte` — the top band: identity row, decision cluster (state-adaptive headline + score + gates + threshold + progress/open), per-theme score grid, strengths + critical gaps, and the action zone (Submit / Approve+Reject / read-only status). Reads stores directly (like the old `ApprovalBanner`); single prop `onPickGap`.
- **Rewrite** `src/lib/components/policy-review/views/ReviewView.svelte` — brand line + band + filter toolbar + three-tier collapsible checklist; owns `openMap`, filters, and the gap-click handler. No longer renders `ApprovalBanner`.
- **Modify** `src/lib/components/policy-review/styles.css` — replace the `.review` / `.review-main` / `.review-side` / `.side-card` / rail rule block with single-column + `.rv-*` band styles; add breakpoints, focus rings, contrast/touch fixes, RTL + reduced-motion entries.
- **Modify** `src/lib/components/policy-review/views/ItemDrawer.svelte` — add `role="dialog"`, `aria-modal`, `aria-labelledby`, focus trap, initial + restore focus, background scroll lock.
- **Delete** `src/lib/components/policy-review/views/ApprovalBanner.svelte` — content folded into the band; remove the now-unused `.approval-banner*` CSS.

Naming contract used across tasks (keep these exact): `ReviewMode = 'reviewer' | 'decide' | 'readonly'`; `ResultCounts` keys `compliant` / `'non-compliant'` / `human` / `pending` / `total`; `Gap` fields `ref`, `title`, `theme`, `sectionId`, `n`, `comment?`; band prop `onPickGap: (sectionId: string, n: number) => void`; collapse map read as `openMap[sec.id] === true` (open).

---

## Task 1: Pure presentation logic + tests

**Files:**
- Create: `src/lib/components/policy-review/lib/reviewView.ts`
- Test: `src/lib/components/policy-review/lib/reviewView.test.ts`

- [ ] **Step 1: Write the failing test**

Create `src/lib/components/policy-review/lib/reviewView.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import {
	resolveMode,
	isLocked,
	countResults,
	openCount,
	resolvedCount,
	itemNumber,
	topGaps,
	initOpenMap
} from './reviewView';
import type { ChecklistVersion, ItemResult, Theme } from './types';

const THEMES: Theme[] = [
	{ id: 'T1', name: 'Policy Foundation', weight: 28, gate: true, threshold: 85 },
	{ id: 'T2', name: 'Governance and Accountability', weight: 28, gate: true, threshold: 85 },
	{ id: 'T3', name: 'People and Communication', weight: 16, gate: false, threshold: 85 }
];

// Each section gets `count` items so we can exercise counts/gaps.
function version(specs: { theme: string; items: number }[]): ChecklistVersion {
	return {
		id: 'v',
		label: 'v',
		status: 'active',
		publishedAt: null,
		publishedBy: null,
		changeSummary: '',
		themes: THEMES,
		verdictBands: { approved: 85, conditional: 70 },
		standards: [],
		sections: specs.map((s, i) => ({
			id: `PRP${i + 1}`,
			theme: s.theme,
			title: `Section ${i + 1}`,
			codes: 'c',
			intent: 'i',
			items: Array.from({ length: s.items }, (_, k) => ({
				id: `PRP${i + 1}-${k + 1}`,
				n: k + 1,
				text: `Item ${i + 1}.${k + 1}`,
				codes: 'OEC',
				assessment: 'auto' as const
			}))
		}))
	};
}

const res = (pairs: Record<string, ItemResult['result']>): Record<string, ItemResult> =>
	Object.fromEntries(Object.entries(pairs).map(([k, v]) => [k, { result: v }]));

describe('resolveMode', () => {
	it('draft + checker → reviewer', () => expect(resolveMode('draft', true, false)).toBe('reviewer'));
	it('rejected + checker → reviewer', () => expect(resolveMode('rejected', true, false)).toBe('reviewer'));
	it('pending + approver → decide', () => expect(resolveMode('pending', false, true)).toBe('decide'));
	it('pending + checker (not approver) → readonly', () => expect(resolveMode('pending', true, false)).toBe('readonly'));
	it('approved + anyone → readonly', () => expect(resolveMode('approved', true, true)).toBe('readonly'));
	it('admin on draft (both gates) → reviewer', () => expect(resolveMode('draft', true, true)).toBe('reviewer'));
	it('admin on pending (both gates) → decide, not reviewer', () => expect(resolveMode('pending', true, true)).toBe('decide'));
});

describe('isLocked', () => {
	it('draft and rejected are editable', () => {
		expect(isLocked('draft')).toBe(false);
		expect(isLocked('rejected')).toBe(false);
	});
	it('pending and approved are locked', () => {
		expect(isLocked('pending')).toBe(true);
		expect(isLocked('approved')).toBe(true);
	});
});

describe('countResults / openCount / resolvedCount', () => {
	const v = version([{ theme: 'T1', items: 2 }, { theme: 'T2', items: 2 }]);
	const c = countResults(
		v,
		res({ 'PRP1-1': 'compliant', 'PRP1-2': 'non-compliant', 'PRP2-1': 'human' })
	); // PRP2-2 missing → pending

	it('tallies every bucket and total', () => {
		expect(c).toEqual({ compliant: 1, 'non-compliant': 1, human: 1, pending: 1, total: 4 });
	});
	it('openCount = human + pending', () => expect(openCount(c)).toBe(2));
	it('resolvedCount = compliant + non-compliant', () => expect(resolvedCount(c)).toBe(2));
});

describe('itemNumber', () => {
	it('strips the PRP prefix and joins with n', () => {
		expect(itemNumber('PRP1', 2)).toBe('1.2');
		expect(itemNumber('PRP12', 3)).toBe('12.3');
	});
});

describe('topGaps', () => {
	it('returns non-compliant items, sorted by theme rank, with stripped ref', () => {
		const v = version([{ theme: 'T3', items: 1 }, { theme: 'T1', items: 1 }]);
		const gaps = topGaps(v, res({ 'PRP1-1': 'non-compliant', 'PRP2-1': 'non-compliant' }));
		expect(gaps.map((g) => g.theme)).toEqual(['T1', 'T3']); // PRP2 is T1 → first
		expect(gaps[0]).toMatchObject({ ref: '2.1', theme: 'T1', sectionId: 'PRP2', n: 1 });
	});
	it('honours the limit', () => {
		const v = version([{ theme: 'T1', items: 6 }]);
		const all = Object.fromEntries(Array.from({ length: 6 }, (_, k) => [`PRP1-${k + 1}`, 'non-compliant']));
		expect(topGaps(v, res(all as Record<string, ItemResult['result']>)).length).toBe(5);
	});
});

describe('initOpenMap', () => {
	it('starts every section collapsed', () => {
		const v = version([{ theme: 'T1', items: 1 }, { theme: 'T2', items: 1 }]);
		expect(initOpenMap(v)).toEqual({ PRP1: false, PRP2: false });
	});
	it('can open all when asked', () => {
		const v = version([{ theme: 'T1', items: 1 }]);
		expect(initOpenMap(v, true)).toEqual({ PRP1: true });
	});
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test:frontend -- src/lib/components/policy-review/lib/reviewView.test.ts`
Expected: FAIL — `Failed to resolve import "./reviewView"` (module does not exist yet).

- [ ] **Step 3: Write the implementation**

Create `src/lib/components/policy-review/lib/reviewView.ts`:

```ts
// Pure presentation logic for the Policy Review detail page.
// No SvelteKit/store imports — kept framework-free so it is unit-testable
// and shared by ReviewView.svelte and ReviewSummaryBand.svelte.

import type { ChecklistVersion, ItemResult, ReviewStatus } from './types';

export type ReviewMode = 'reviewer' | 'decide' | 'readonly';

// Which interaction mode the page is in, given review state + role.
// Order matters: a pending review for an approver is a DECISION, even for an
// admin who also satisfies canUseChecker.
export function resolveMode(
	status: ReviewStatus,
	canUseChecker: boolean,
	canApprove: boolean
): ReviewMode {
	if (status === 'pending' && canApprove) return 'decide';
	if ((status === 'draft' || status === 'rejected') && canUseChecker) return 'reviewer';
	return 'readonly';
}

// Items are editable only while the review is draft or rejected.
export function isLocked(status: ReviewStatus): boolean {
	return status !== 'draft' && status !== 'rejected';
}

export interface ResultCounts {
	compliant: number;
	'non-compliant': number;
	human: number;
	pending: number;
	total: number;
}

export function countResults(
	version: ChecklistVersion,
	results: Record<string, ItemResult>
): ResultCounts {
	const c: ResultCounts = { compliant: 0, 'non-compliant': 0, human: 0, pending: 0, total: 0 };
	version.sections.forEach((sec) =>
		sec.items.forEach((it) => {
			const r = results[it.id]?.result ?? 'pending';
			c[r] += 1;
			c.total += 1;
		})
	);
	return c;
}

export function openCount(c: ResultCounts): number {
	return c.human + c.pending;
}

export function resolvedCount(c: ResultCounts): number {
	return c.compliant + c['non-compliant'];
}

// Display number for an item: 'PRP1' + n 2 → '1.2'. The PRP prefix is stripped.
export function itemNumber(sectionId: string, n: number): string {
	return `${sectionId.replace('PRP', '')}.${n}`;
}

export interface Gap {
	ref: string; // '1.4'
	title: string;
	theme: string; // 'T1'
	sectionId: string; // 'PRP1'
	n: number;
	comment?: string;
}

const THEME_RANK: Record<string, number> = { T1: 0, T2: 1, T3: 2, T4: 3, T5: 4, T6: 5 };

// Non-compliant items, ranked T1→T6 (unranked last), capped at `limit`.
export function topGaps(
	version: ChecklistVersion,
	results: Record<string, ItemResult>,
	limit = 5
): Gap[] {
	const gaps: Gap[] = [];
	version.sections.forEach((sec) =>
		sec.items.forEach((it) => {
			const r = results[it.id] ?? { result: 'pending' as const };
			if (r.result === 'non-compliant') {
				gaps.push({
					ref: itemNumber(sec.id, it.n),
					title: it.text,
					theme: sec.theme,
					sectionId: sec.id,
					n: it.n,
					comment: r.comment
				});
			}
		})
	);
	gaps.sort((a, b) => (THEME_RANK[a.theme] ?? 9) - (THEME_RANK[b.theme] ?? 9));
	return gaps.slice(0, limit);
}

// Collapsed-by-default disclosure map. This deliberately inverts the legacy
// behaviour where a missing key meant "open"; every PRP group starts closed.
export function initOpenMap(version: ChecklistVersion, open = false): Record<string, boolean> {
	const m: Record<string, boolean> = {};
	version.sections.forEach((s) => (m[s.id] = open));
	return m;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm run test:frontend -- src/lib/components/policy-review/lib/reviewView.test.ts`
Expected: PASS — all describe blocks green.

- [ ] **Step 5: Type-check**

Run: `npm run check`
Expected: 0 errors in the two new files (pre-existing warnings elsewhere are fine).

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/policy-review/lib/reviewView.ts src/lib/components/policy-review/lib/reviewView.test.ts
git commit -m "feat(policy-review): pure review-view logic (mode/counts/gaps/openMap) + tests"
```

---

## Task 2: ReviewSummaryBand component

**Files:**
- Create: `src/lib/components/policy-review/views/ReviewSummaryBand.svelte`

This component renders the top band and owns the approve/reject and replace-document interactions (ported from `ApprovalBanner.svelte` and `ReviewView.svelte`). It is not wired into the page until Task 4, so the app keeps working at this commit. Styles come in Task 3 (it will look unstyled until then — acceptable mid-build).

> **Depends on Task 1** — `reviewView.ts` (with `resolveMode`, `isLocked`, `countResults`, `openCount`, `resolvedCount`, `topGaps`, and the `Gap` type) must already exist for this component's imports and the Step 2 type-check to resolve. Implement tasks in order.

- [ ] **Step 1: Create the component**

Create `src/lib/components/policy-review/views/ReviewSummaryBand.svelte`:

```svelte
<script lang="ts">
	// Overview band — state-adaptive summary + decision header for the review page.
	// Absorbs the old right rail (Decision / Score by Theme / Strengths / Gaps) and
	// the old ApprovalBanner (pending / approved / rejected status + approve/reject).
	import Icon from '../ui/Icon.svelte';
	import VerdictBadge from '../ui/VerdictBadge.svelte';
	import { computeScores } from '../lib/scoring';
	import {
		resolveMode,
		isLocked,
		countResults,
		openCount as openCountOf,
		resolvedCount,
		topGaps,
		type Gap
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
	let locked = $derived(review ? isLocked(review.status) : true);
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
	let replaceInput: HTMLInputElement;
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
	let rejectOpen = $state(false);
	let rejectNote = $state('');
	async function approve() {
		if (!review) return;
		approvalError = '';
		try {
			await approveAndPublish(review.id);
		} catch (e) {
			approvalError = String(e);
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
		if (approval.status === 'pending') return `Submitted for approval — awaiting OE approver · ${approval.sentAt ?? ''}`;
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
				<span class="rv-stat-l">Issue threshold</span>
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
					<div class="rv-decide-actions">
						<button class="btn btn-primary" type="button" onclick={approve}>Approve &amp; Publish</button>
						{#if !rejectOpen}
							<button class="btn" type="button" onclick={openReject}>Reject</button>
						{/if}
					</div>
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
					{#each strengths as s, i (i)}
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
```

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: 0 errors in `ReviewSummaryBand.svelte`. (Confirm `reviewDocumentUrl`, `submitModalOpen`, `approveAndPublish`, `rejectPolicy`, `replaceDocument` all exist in `../lib/store` / `../lib/api` — they do per the current `ReviewView.svelte` / `ApprovalBanner.svelte` / `store.ts`.)

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/policy-review/views/ReviewSummaryBand.svelte
git commit -m "feat(policy-review): add ReviewSummaryBand (overview band, not yet wired)"
```

---

## Task 3: Band styles

**Files:**
- Modify: `src/lib/components/policy-review/styles.css`

Add the `.rv-*` band styles. Insert this block immediately BEFORE the `/* ── review layout ── minimalist ───── */` comment (currently around line 511), still inside `@scope (.pr-root)`. It reuses existing component classes (`.verdict-badge`, `.theme-score-row`, `.theme-score-bar`, `.gap-list`, `.gap-item`, `.btn*`, `.gate-mini`, `.editor-grid`, `.btn-danger`).

- [ ] **Step 1: Add the band CSS**

```css
/* ── overview band (ReviewSummaryBand) ───────────────── */
.rv-band { display: flex; flex-direction: column; gap: 22px; padding: 28px 0 24px; border-bottom: 1px solid var(--ink-100); margin-bottom: 28px; }

.rv-identity { display: flex; align-items: flex-start; gap: 24px; }
.rv-eyebrow { font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-500); }
.rv-title { font-size: 24px; font-weight: 600; letter-spacing: -0.015em; margin: 6px 0 8px; color: var(--ink-900); }
.rv-meta { display: flex; flex-wrap: wrap; gap: 10px; font-size: 11.5px; color: var(--ink-500); font-family: var(--mono); }
.rv-meta .sep { color: var(--ink-200); }
.rv-source { display: flex; align-items: center; gap: 12px; margin-top: 10px; font-size: 12.5px; }
.rv-source .src-link { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-700); }
.rv-source .src-link:hover { color: var(--primary); }
.rv-source .src-dl { color: var(--primary); font-weight: 600; }
.rv-source .src-replace { background: none; border: 0; color: var(--primary); font-weight: 600; cursor: pointer; font-size: 12.5px; padding: 0; }
.rv-source .src-replace[disabled] { opacity: 0.5; cursor: not-allowed; }

.rv-decision { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 14px 28px; padding-top: 18px; border-top: 1px solid var(--ink-100); }
.rv-stat { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.rv-stat-l { font-size: 10.5px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-500); }
.rv-stat-v { font-size: 13.5px; font-weight: 500; color: var(--ink-900); font-variant-numeric: tabular-nums; }
.rv-score { font-size: 30px; font-weight: 500; letter-spacing: -0.02em; line-height: 1; color: var(--ink-900); font-variant-numeric: tabular-nums; }
.rv-score .pct { font-size: 15px; color: var(--ink-300); font-weight: 400; margin-left: 2px; }

.rv-action { margin-left: auto; display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.rv-action .btn-primary { padding: 10px 16px; }
.rv-decide-actions { display: flex; gap: 8px; }
.rv-hint { font-size: 11.5px; color: var(--ink-500); }
.rv-status { font-size: 12.5px; font-weight: 500; }
.rv-status.pending { color: var(--info); }
.rv-status.approved { color: var(--ok); }
.rv-status.rejected { color: var(--bad); }

.rv-reject-note { font-size: 12.5px; color: var(--ink-700); font-style: italic; padding: 10px 12px; background: var(--bad-50); border: 1px solid #F0CCCC; border-radius: 8px; }
.rv-reject-form { margin-top: 4px; }
.rv-reject-buttons { display: flex; justify-content: flex-end; gap: 8px; }
.rv-error { font-size: 12.5px; color: var(--bad); padding: 8px 12px; background: var(--bad-bg); border: 1px solid #F0CCCC; border-radius: 8px; }

.rv-theme-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 4px 28px; }
.rv-theme { min-width: 0; }

.rv-split { display: grid; grid-template-columns: 1fr 1fr; gap: 28px; }
.rv-h { margin: 0 0 14px; font-size: 10.5px; font-weight: 500; color: var(--ink-500); text-transform: uppercase; letter-spacing: 0.08em; }
.rv-empty { font-size: 12.5px; color: var(--ink-500); }
.rv-gap { width: 100%; text-align: left; background: none; border: 0; padding: 0; font: inherit; color: inherit; cursor: pointer; border-radius: 6px; }
.rv-gap:hover .rv-gap-title { color: var(--primary); }
.rv-gap-title { color: var(--ink-900); font-weight: 500; margin-bottom: 2px; }
.rv-gap-ref { font-size: 11.5px; color: var(--ink-500); font-family: var(--mono); }
```

- [ ] **Step 2: Verify it parses**

Run: `npm run check`
Expected: 0 new errors.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/policy-review/styles.css
git commit -m "style(policy-review): overview band styles"
```

---

## Task 4: Rewrite ReviewView to overview-first

**Files:**
- Rewrite: `src/lib/components/policy-review/views/ReviewView.svelte`

Replace the whole file. The brand line (`.pl-brand-line`, already defined) sits full-width above the max-width `.review` column. The band renders first; then the filter toolbar; then the three-tier checklist with `openMap[sec.id] === true` semantics, `aria-expanded` on PRP headers, and a gap-click handler that expands the PRP group and opens the drawer. `ApprovalBanner` is no longer imported.

> **Collapse semantics:** `isOpen = openMap[sec.id] === true` is what toggles the existing `.section.open` CSS class (kept in Task 5). This deliberately inverts the legacy `openMap[id] !== false` default (which meant "open"); keep the `=== true` check and `initOpenMap` defaults in sync or sections will silently re-expand.

- [ ] **Step 1: Replace the file contents**

```svelte
<script lang="ts">
	// Review stage — overview band on top, three-tier collapsible checklist below.
	import Icon from '../ui/Icon.svelte';
	import StatusCircle from '../ui/StatusCircle.svelte';
	import ReviewSummaryBand from './ReviewSummaryBand.svelte';
	import { computeScores } from '../lib/scoring';
	import { countResults, initOpenMap, itemNumber } from '../lib/reviewView';
	import type { Section, ChecklistItemDef, ItemResult } from '../lib/types';
	import { activeReview, activeVersion, picked, drawerOpen } from '../lib/store';

	type Filter = 'all' | 'issues' | 'human' | 'compliant';

	let openMap = $state<Record<string, boolean>>({});
	let filter = $state<Filter>('all');

	let version = $derived($activeVersion);
	let sectionsList = $derived(version?.sections ?? []);
	let themesList = $derived(version?.themes ?? []);
	let results = $derived($activeReview?.results ?? {});

	// Collapsed by default: (re)initialise the open map whenever the checklist
	// version changes. Sections start closed; the user opens what they want.
	let lastVersionId = '';
	$effect(() => {
		const id = version?.id ?? '';
		if (id !== lastVersionId) {
			lastVersionId = id;
			openMap = version ? initOpenMap(version) : {};
		}
	});

	let scoreResult = $derived(version ? computeScores(version, results) : null);
	let counts = $derived(
		version
			? countResults(version, results)
			: { compliant: 0, 'non-compliant': 0, human: 0, pending: 0, total: 0 }
	);
	let totalItems = $derived(counts.total);

	let byTheme = $derived.by(() => {
		const out: Record<string, Section[]> = {};
		themesList.forEach((t) => (out[t.id] = []));
		sectionsList.forEach((s) => out[s.theme]?.push(s));
		return out;
	});

	function rOf(sec: Section, it: ChecklistItemDef): ItemResult {
		return results[it.id] ?? { result: 'pending' };
	}

	function itemMatchesFilter(sec: Section, it: ChecklistItemDef): boolean {
		const r = rOf(sec, it).result;
		if (filter === 'all') return true;
		if (filter === 'issues') return r === 'non-compliant';
		if (filter === 'human') return r === 'human';
		if (filter === 'compliant') return r === 'compliant';
		return true;
	}

	function sectionVisibleItems(sec: Section): ChecklistItemDef[] {
		return sec.items.filter((it) => itemMatchesFilter(sec, it));
	}

	function themeHasVisible(themeId: string): Section[] {
		return (byTheme[themeId] ?? []).filter((sec) =>
			sec.items.some((it) => itemMatchesFilter(sec, it))
		);
	}

	function sectionCounts(sec: Section): Record<string, number> {
		return sec.items.reduce(
			(a, it) => {
				const r = rOf(sec, it).result;
				a[r] = (a[r] || 0) + 1;
				return a;
			},
			{} as Record<string, number>
		);
	}

	function setOpen(id: string, v: boolean) {
		openMap = { ...openMap, [id]: v };
	}
	function expandAll() {
		openMap = version ? initOpenMap(version, true) : {};
	}
	function collapseAll() {
		openMap = version ? initOpenMap(version, false) : {};
	}

	function pickItem(sec: Section, it: ChecklistItemDef) {
		picked.set({ sectionId: sec.id, n: it.n });
		drawerOpen.set(true);
	}

	// A critical gap click: reveal the PRP group, then open the item drawer.
	function pickGap(sectionId: string, n: number) {
		openMap = { ...openMap, [sectionId]: true };
		picked.set({ sectionId, n });
		drawerOpen.set(true);
	}

	function selectedKey(sec: Section, it: ChecklistItemDef): boolean {
		const p = $picked;
		return !!p && p.sectionId === sec.id && p.n === it.n;
	}
</script>

<div class="pl-brand-line"></div>
<div class="review">
	<ReviewSummaryBand onPickGap={pickGap} />

	<!-- Filters -->
	<div class="review-toolbar">
		<button class="chip" class:active={filter === 'all'} aria-pressed={filter === 'all'} onclick={() => (filter = 'all')} type="button">
			All <span class="count">{totalItems}</span>
		</button>
		<button class="chip" class:active={filter === 'issues'} aria-pressed={filter === 'issues'} onclick={() => (filter = 'issues')} type="button">
			<Icon name="alert" size={12} /> Non-Compliant <span class="count">{counts['non-compliant'] || 0}</span>
		</button>
		<button class="chip" class:active={filter === 'human'} aria-pressed={filter === 'human'} onclick={() => (filter = 'human')} type="button">
			<Icon name="user" size={12} /> Needs Human <span class="count">{counts.human || 0}</span>
		</button>
		<button class="chip" class:active={filter === 'compliant'} aria-pressed={filter === 'compliant'} onclick={() => (filter = 'compliant')} type="button">
			<Icon name="check" size={12} stroke={3} /> Compliant <span class="count">{counts.compliant || 0}</span>
		</button>
		<div style="flex:1"></div>
		<button class="btn btn-sm btn-ghost" onclick={expandAll} type="button"><Icon name="chevD" size={12} /> Expand all</button>
		<button class="btn btn-sm btn-ghost" onclick={collapseAll} type="button"><Icon name="chevR" size={12} /> Collapse</button>
	</div>

	<!-- Themes -->
	{#each themesList as theme (theme.id)}
		{@const visibleSecs = themeHasVisible(theme.id)}
		{#if visibleSecs.length > 0}
			{@const themeData = scoreResult?.themeRows.find((t) => t.id === theme.id)}
			{#if themeData}
				<div class="theme">
					<div class="theme-head">
						<h2>
							<span class="theme-id {theme.id.toLowerCase()}">{theme.id}</span>
							{theme.name}
							{#if theme.gate}<span class="gate-tag">MANDATORY GATE</span>{/if}
						</h2>
						<div class="theme-stats">
							<span><b>{themeData.pct}%</b> score</span>
							<span>{themeData.yes}/{themeData.total} compliant</span>
							{#if themeData.human}<span>{themeData.human} human</span>{/if}
							<span><b>{theme.weight}%</b> weight</span>
						</div>
					</div>

					{#each visibleSecs as sec (sec.id)}
						{@const isOpen = openMap[sec.id] === true}
						{@const items = sectionVisibleItems(sec)}
						{@const c = sectionCounts(sec)}
						{#if items.length > 0 || filter === 'all'}
							<div class="section" class:open={isOpen}>
								<button class="sec-head" aria-expanded={isOpen} aria-controls="sec-{sec.id}" onclick={() => setOpen(sec.id, !isOpen)} type="button">
									<div class="left">
										<span class="chev"><Icon name="chevR" size={14} /></span>
										<div class="titleblock">
											<div class="prp">{sec.id} · {sec.codes}</div>
											<h3>{sec.title}</h3>
											<div class="intent">{sec.intent}</div>
										</div>
									</div>
									<div class="right">
										{#if c.compliant}<span class="minibadge ok"><span class="dot"></span>{c.compliant}</span>{/if}
										{#if c['non-compliant']}<span class="minibadge bad"><span class="dot"></span>{c['non-compliant']}</span>{/if}
										{#if c.human}<span class="minibadge warn"><span class="dot"></span>{c.human}</span>{/if}
									</div>
								</button>

								{#if isOpen}
									<div class="sec-body" id="sec-{sec.id}">
										{#each items as it (it.n)}
											{@const ans = rOf(sec, it)}
											<button class="item-row" class:selected={selectedKey(sec, it)} onclick={() => pickItem(sec, it)} type="button">
												<div class="item-num">{itemNumber(sec.id, it.n)}</div>
												<div class="item-status"><StatusCircle result={ans.result} /></div>
												<div class="item-text">
													{it.text}
													<div class="meta">
														<span>{it.codes}</span>
														{#if ans.confidence != null && ans.result !== 'human'}
															<span class="conf">confidence {Math.round(ans.confidence * 100)}%</span>
														{/if}
														{#if ans.reviewed}<span style="color:var(--primary)">· deep-reviewed</span>{/if}
														{#if ans.edited}<span style="color:var(--ink-500)">· edited</span>{/if}
													</div>
												</div>
												<div class="item-arrow"><Icon name="chevR" size={14} /></div>
											</button>
										{/each}
									</div>
								{/if}
							</div>
						{/if}
					{/each}
				</div>
			{/if}
		{/if}
	{/each}
</div>
```

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: 0 errors in `ReviewView.svelte`. (`ApprovalBanner` import is gone; `VerdictBadge` is no longer used here — make sure no dangling import remains. The file above already omits both.)

- [ ] **Step 3: Manual smoke (app running per project run notes)**

Open a `draft` review and confirm: brand line + band on top; PRP groups are **collapsed**; clicking a PRP header expands it (chevron rotates) and shows items; clicking an item opens the drawer; arrow keys still cycle items; Expand all / Collapse work; filters change the visible items; clicking a critical gap in the band expands its PRP group and opens that item.
Expected: all behaviors as described; no console errors.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/policy-review/views/ReviewView.svelte
git commit -m "feat(policy-review): overview-first ReviewView (band + collapsed 3-tier checklist)"
```

---

## Task 5: Single-column layout + checklist style refinements

**Files:**
- Modify: `src/lib/components/policy-review/styles.css`

Replace the old two-column review layout and the rail card styles, then bump failing-contrast micro-text and add focus rings.

- [ ] **Step 1: Replace the review layout rules**

Find this block (currently around lines 511–514):

```css
/* ── review layout ── minimalist ───────────────────── */
.review { display: grid; grid-template-columns: minmax(0,1fr) 340px; gap: 0; height: 100%; min-height: 0; }
.review-main { overflow-y: auto; padding: 36px 40px 96px; min-width: 0; }
.review-side { overflow-y: auto; border-left: 1px solid var(--ink-100); background: var(--white); padding: 36px 28px; }
```

Replace it with:

```css
/* ── review layout ── single column ─────────────────── */
.review { max-width: 1120px; margin: 0 auto; padding: 0 40px 96px; min-width: 0; }
```

- [ ] **Step 2: Delete the now-unused rail/side-card rules**

Delete the entire `/* ── side rail — flat sections, no card boxes ─── */` block — every rule from `.side-card` through `.gap-item.strength .n` and the `.review-side .btn-primary` rule (currently around lines 664–709). The band reuses `.theme-score-row`, `.theme-score-bar`, `.gap-list`, and `.gap-item` (keep those), so delete only: `.side-card`, `.side-card:last-child`, `.side-card h4`, `.score-block`, `.score-block .num`, `.score-block .num .pct`, `.score-block .lbl`, `.decision-summary`, `.decision-summary .row*`, and `.review-side .btn-primary`.

- [ ] **Step 3: Add contrast + focus-visible fixes**

Append inside `@scope (.pr-root)` (e.g. right after the band block from Task 3):

```css
/* ── review a11y: contrast + focus ──────────────────── */
.item-num, .item-text .meta, .item-text .meta .conf, .sec-head .prp, .chip .count { color: var(--ink-500); }
.chip:focus-visible,
.sec-head:focus-visible,
.item-row:focus-visible,
.rv-gap:focus-visible {
	outline: 2px solid var(--primary-100);
	outline-offset: -2px;
	border-radius: 6px;
}

/* Touch targets — keep interactive rows/controls comfortably tappable */
.item-row { min-height: 44px; }
.sec-head { min-height: 48px; }
.chip { min-height: 36px; }
.rv-action .btn, .rv-decide-actions .btn { min-height: 40px; }
```

(The focus-ring uses the same `outline: 2px var(--primary-100)` recipe the existing inputs use at styles.css:759, so it stays visually consistent with the rest of the tool.)

- [ ] **Step 4: Type-check + manual smoke**

Run: `npm run check`
Expected: 0 new errors.
Manual (app running): the review page is a single centered column (no right rail); the band's theme bars and gaps render with their existing styling; keyboard-tabbing through filters / PRP headers / items / gaps shows a visible focus ring; micro-text (item numbers, meta) is a touch darker.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/policy-review/styles.css
git commit -m "style(policy-review): single-column review layout, drop rail, a11y contrast/focus"
```

---

## Task 6: Responsive + RTL + reduced-motion

**Files:**
- Modify: `src/lib/components/policy-review/styles.css`

- [ ] **Step 1: Add the responsive block**

Append inside `@scope (.pr-root)`, just before the existing `/* ── RTL hardening ── */` section:

```css
/* ── review responsive ──────────────────────────────── */
@media (max-width: 1024px) {
	.review { padding: 0 24px 80px; }
	.rv-theme-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 768px) {
	.rv-theme-grid { grid-template-columns: 1fr; }
	.rv-split { grid-template-columns: 1fr; }
	.rv-action { margin-left: 0; align-items: flex-start; width: 100%; }
}
@media (max-width: 640px) {
	.review { padding: 0 16px 72px; }
	.drawer { width: 100%; max-width: 100%; }
}
```

- [ ] **Step 2: Extend RTL + reduced-motion**

In the `/* ── RTL hardening ── */` section, add:

```css
:dir(rtl) .sec-head .chev { transform: scaleX(-1); }
:dir(rtl) .section.open .sec-head .chev { transform: scaleX(-1) rotate(90deg); }
:dir(rtl) .rv-action { margin-left: 0; margin-right: auto; }
```

In the `@media (prefers-reduced-motion: reduce)` block, add `.sec-head .chev, .item-row, .rv-gap` to the selector list so their transitions are neutralised too.

- [ ] **Step 3: Verify responsive**

Run: `npm run check` → 0 new errors.
Manual (app running): use the browser/preview at ~1280 / ~1024 / ~768 / ~480px widths — the band clusters reflow, the theme grid drops to 2 then 1 column, strengths/gaps stack, the action zone moves below, and the drawer fills the screen on the narrowest width. No horizontal scrollbar appears.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/policy-review/styles.css
git commit -m "style(policy-review): responsive breakpoints, RTL chevrons, reduced-motion"
```

---

## Task 7: Item drawer accessibility

**Files:**
- Modify: `src/lib/components/policy-review/views/ItemDrawer.svelte`

Add dialog semantics, focus management, and background scroll lock. Keyboard cycling (Arrow/Escape) already lives in `PolicyReviewApp.svelte` and stays as-is.

- [ ] **Step 1: Add a heading id, dialog roles, and focus/scroll effect**

In the populated branch (`{:else}` ... `<aside class="drawer" ...>`), change the `<aside>` opening tag and the `<h2>` to:

```svelte
	<aside
		class="drawer"
		class:open={$drawerOpen}
		role="dialog"
		aria-modal="true"
		aria-labelledby="pr-drawer-title"
		bind:this={drawerEl}
	>
```

```svelte
				<h2 id="pr-drawer-title">{def.text}</h2>
```

Add to the `<script>` (near the other `$state`/`$effect` declarations):

```ts
	let drawerEl: HTMLElement | undefined = $state();

	// While open: lock background scroll, move focus into the drawer, and trap
	// Tab inside it. Restore focus to the previously-focused element on close.
	$effect(() => {
		if (!$drawerOpen || !drawerEl) return;
		const prevActive = document.activeElement as HTMLElement | null;
		const prevOverflow = document.body.style.overflow;
		document.body.style.overflow = 'hidden';

		const focusables = () =>
			Array.from(
				drawerEl!.querySelectorAll<HTMLElement>(
					'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
				)
			).filter((el) => !el.hasAttribute('disabled'));

		focusables()[0]?.focus();

		function onKeydown(e: KeyboardEvent) {
			if (e.key !== 'Tab') return;
			const els = focusables();
			if (els.length === 0) return;
			const first = els[0];
			const last = els[els.length - 1];
			if (e.shiftKey && document.activeElement === first) {
				e.preventDefault();
				last.focus();
			} else if (!e.shiftKey && document.activeElement === last) {
				e.preventDefault();
				first.focus();
			}
		}
		drawerEl.addEventListener('keydown', onKeydown);

		return () => {
			drawerEl?.removeEventListener('keydown', onKeydown);
			document.body.style.overflow = prevOverflow;
			prevActive?.focus?.();
		};
	});
```

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: 0 errors in `ItemDrawer.svelte`.

- [ ] **Step 3: Manual smoke (app running)**

Open an item drawer: focus lands inside it; Tab cycles within the drawer and does not escape to the page behind; the page behind does not scroll; Escape closes it (existing behavior) and focus returns to the item row you opened it from.
Expected: all as described.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/policy-review/views/ItemDrawer.svelte
git commit -m "a11y(policy-review): drawer dialog role, focus trap, scroll lock"
```

---

## Task 8: Remove the obsolete ApprovalBanner

**Files:**
- Delete: `src/lib/components/policy-review/views/ApprovalBanner.svelte`
- Modify: `src/lib/components/policy-review/styles.css`

The band now covers every approval state and the approve/reject flow. `ReviewView` stopped importing `ApprovalBanner` in Task 4.

- [ ] **Step 1: Confirm nothing imports it**

Run: `git grep -n "ApprovalBanner"`
Expected: no matches (Task 4 removed the import/usage). If any remain, remove them before deleting the file.

- [ ] **Step 2: Delete the component and its CSS**

```bash
git rm src/lib/components/policy-review/views/ApprovalBanner.svelte
```

In `styles.css`, delete the entire `/* ── approval / submit modal ── */`-adjacent `.approval-banner*` rule group (currently around lines 780–802: from `.approval-banner {` through `.approval-banner .btn-danger[disabled] { ... }`). Leave the `.modal*` rules (used by `SubmitApprovalModal`).

- [ ] **Step 3: Type-check**

Run: `npm run check`
Expected: 0 errors; no "unused"/"cannot find" for `ApprovalBanner`.

- [ ] **Step 4: Commit**

```bash
git add -A src/lib/components/policy-review
git commit -m "chore(policy-review): remove ApprovalBanner (folded into the band)"
```

---

## Task 9: Full verification sweep

**Files:** none (verification only)

- [ ] **Step 1: Static gates**

Run: `npm run test:frontend` → all policy-review unit tests pass (including the new `reviewView.test.ts` and the existing `scoring.test.ts`).
Run: `npm run check` → no new errors.
Run: `npm run lint:frontend` → no new lint errors in touched files.

- [ ] **Step 2: State-matrix manual smoke (app running per project run notes)**

For each row, open a review in that state/role and confirm the band + checklist behave per the spec's state matrix:
- `draft` · checker → reviewer band (progress + open-items), Submit enabled only when no open items, checklist editable (drawer Override/Save work), Replace shown.
- `rejected` · checker → reviewer band + the quoted rejection note visible; Submit resubmits; editable.
- `pending` · approver → decision band, Approve & Publish + Reject (Reject requires a note), checklist read-only (drawer has no working Save).
- `pending` · checker (not approver) → read-only "Submitted — awaiting OE approver" status, no decision buttons.
- `approved` · any → "Approved & published by … · …" recorded headline, read-only.

Also confirm: the issue threshold shows the value from the checklist version's `verdictBands.approved` (not a hard-coded 85 if a non-default version is active); critical-gap click expands + opens the right item; nothing from the old rail or approval banner is missing.

- [ ] **Step 3: Accessibility + responsive spot-check**

Keyboard-only: tab to a PRP header, Enter toggles it (`aria-expanded` flips); filter chips expose `aria-pressed`; focus rings visible; drawer traps focus. Resize to ~768 and ~480px: no horizontal scroll, clusters stack, drawer full-width. If an Arabic/RTL locale is available, confirm chevrons and the action zone mirror correctly.

- [ ] **Step 4: No style leak**

Confirm the rest of Osool (chat, settings) is visually unchanged — all new rules are inside `@scope (.pr-root)`.

- [ ] **Step 5: Final commit (if any tidy-ups were needed)**

```bash
git add -A src/lib/components/policy-review
git commit -m "test(policy-review): verification sweep tidy-ups" || echo "nothing to commit"
```

---

## Self-review checklist (completed by plan author)

- **Spec coverage:** overview band (T2/T3), state-adaptive matrix (T2), three-tier collapsed-by-default hierarchy + inversion (T1/T4), rail rehoming (T2/T3/T5), drawer retained + a11y (T7), ApprovalBanner folded in (T2/T8), visual-language reuse (T2/T3), responsive/RTL/contrast/focus (T5/T6), threshold from `verdictBands` (T2), clickable gaps (T2/T4) — all mapped.
- **Placeholders:** none — every code/CSS step shows full content; commands have expected output.
- **Naming consistency:** `ReviewMode`, `ResultCounts`, `Gap`, `onPickGap`, `openMap[id] === true`, `itemNumber`, `initOpenMap` used identically across Tasks 1/2/4. Band reuses existing `.theme-score-row/.theme-score-bar/.gap-list/.gap-item` (kept in Task 5).
