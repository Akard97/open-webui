# Policy Review finalization — Plan 2: Role-aware shell + lifecycle views

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the tool's placeholder shell with a lean, role-aware sidebar and six routed views, and wire the full maker-checker lifecycle UI: an Overview landing, My reviews, an Approval queue, and reviewer↔approver hand-off with locking and publish-to-library.

**Architecture:** The store from Plan 1 already holds `reviews[]`, `activeReviewId`, derived `myReviews`/`approvalQueue`/`publishedPolicies`, and the lifecycle mutators. Plan 2 adds navigation helpers (`openReview`, `goNewReview`), a pure `lib/reviews.ts` summary helper, three new view components, a rewritten role-aware `ToolSidebar`, and 6-view routing in `PolicyReviewApp`. The review workspace (`ReviewView` + `ApprovalBanner`) is reused for both the reviewer's editing context (draft/returned) and the approver's read-only decision context (pending) — locking and the approver buttons already exist from Plan 1.

**Tech Stack:** SvelteKit, TypeScript, Svelte 5 runes, Vitest 1.6 (logic tests), `svelte-check`.

**Spec:** `docs/superpowers/specs/2026-06-14-policy-review-finalization-design.md` (§2 IA, §3 lifecycle, §4 journeys).
**Builds on:** `docs/superpowers/plans/2026-06-14-policy-review-finalization-1-foundation.md` (DONE).

**Conventions:**
- Run one test file: `npx vitest run <path>` · all: `npx vitest run src/lib/components/policy-review/`
- Type-check: `npm run check` (gate = no NEW errors under `src/lib/components/policy-review/`; the project has ~300 unrelated pre-existing errors elsewhere).
- New components use a scoped `<style>` block with the existing CSS variables (`--ink-100..900`, `--primary`, `--primary-50`, `--ok`, `--bad`, `--warn`, `--mono`) so they stay on-theme without depending on shared class names.
- **Scope boundary:** the **Admin** sidebar entry + page are NOT in this plan — they are Plan 3, added together so every visible nav item works. Plan 2's `ViewKey` therefore does NOT include `admin`.

---

### Task 1: Expand `ViewKey` + add navigation helpers to the store

**Files:**
- Modify: `src/lib/components/policy-review/lib/types.ts` (the `ViewKey` line)
- Modify: `src/lib/components/policy-review/lib/store.ts` (default view, view validation, helpers)
- Modify: `src/lib/components/policy-review/lib/store.test.ts` (add nav tests)

- [ ] **Step 1: Widen `ViewKey`**

In `types.ts`, replace:
```ts
export type ViewKey = 'all-policies' | 'new-review';
```
with:
```ts
export type ViewKey = 'overview' | 'library' | 'new-review' | 'my-reviews' | 'approvals' | 'review';
```

- [ ] **Step 2: Update store defaults + validation + helpers**

In `store.ts`:

(a) In `freshInitial()`, change `view: 'all-policies'` to `view: 'overview'`.

(b) In `loadInitial()`, validate the persisted view against the allowed set so a stale `'all-policies'` (or any unknown value) falls back cleanly. Replace the `view: parsed.view ?? 'overview'` line (currently `?? 'all-policies'`) with:
```ts
				view: (
					['overview', 'library', 'new-review', 'my-reviews', 'approvals', 'review'] as const
				).includes(parsed.view as ViewKey)
					? (parsed.view as ViewKey)
					: 'overview',
```

(c) Add navigation helpers near the other mutators (after `resetReview`):
```ts
// Open an existing review in the workspace (used by My reviews + Approval queue).
export function openReview(id: string): void {
	activeReviewId.set(id);
	view.set('review');
}

// Start the new-review wizard from a fresh draft.
export function goNewReview(): void {
	resetReview(); // fresh rev-active, stage = 'upload', activeReviewId = 'rev-active'
	view.set('new-review');
}
```

- [ ] **Step 3: Add nav tests to `store.test.ts`**

Append this describe block to `store.test.ts` (and add `view`, `stage`, `openReview`, `goNewReview` to the existing import from `./store`):
```ts
import { view, stage, openReview, goNewReview } from './store';

describe('navigation helpers', () => {
	it('openReview selects the review and routes to the workspace', () => {
		openReview('rev-pending-1');
		expect(get(activeReviewId)).toBe('rev-pending-1');
		expect(get(view)).toBe('review');
	});

	it('goNewReview resets to a fresh upload wizard', () => {
		goNewReview();
		expect(get(view)).toBe('new-review');
		expect(get(stage)).toBe('upload');
		expect(get(activeReviewId)).toBe('rev-active');
	});
});
```
(If `view`/`stage` are already imported in the file, merge rather than duplicate the import.)

- [ ] **Step 4: Run tests**

Run: `npx vitest run src/lib/components/policy-review/lib/store.test.ts`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**
```bash
git add src/lib/components/policy-review/lib/types.ts src/lib/components/policy-review/lib/store.ts src/lib/components/policy-review/lib/store.test.ts
git commit -m "feat(policy-review): widen ViewKey + openReview/goNewReview nav helpers"
```

---

### Task 2: Pure review-summary helper (`lib/reviews.ts`)

List views need a per-review score/verdict/open-item count. Extract it as a pure, tested helper.

**Files:**
- Create: `src/lib/components/policy-review/lib/reviews.ts`
- Test: `src/lib/components/policy-review/lib/reviews.test.ts`

- [ ] **Step 1: Write the failing test**

Create `reviews.test.ts`:
```ts
import { describe, it, expect } from 'vitest';
import { buildActiveVersion, buildSeedReviews } from './seed';
import { versionFor, summarizeReview, REVIEW_STATUS_META } from './reviews';

const versions = [buildActiveVersion()];
const reviews = buildSeedReviews();
const byId = (id: string) => reviews.find((r) => r.id === id)!;

describe('versionFor', () => {
	it('resolves the snapshot version a review was created against', () => {
		const v = versionFor(byId('rev-active'), versions);
		expect(v?.id).toBe('v2.0');
	});
	it('falls back to the active version when the snapshot id is unknown', () => {
		const v = versionFor({ ...byId('rev-active'), checklistVersionId: 'nope' }, versions);
		expect(v?.status).toBe('active');
	});
});

describe('summarizeReview', () => {
	it('reports a numeric score and verdict for a fully-answered review', () => {
		const s = summarizeReview(byId('rev-pending-1'), versions[0]);
		expect(typeof s.overall).toBe('number');
		expect(s.open).toBe(0); // pending review has no unresolved items
		expect(['approved', 'conditional', 'rejected']).toContain(s.verdictKey);
	});
	it('counts unresolved (human + pending) items as open for an in-progress review', () => {
		const s = summarizeReview(byId('rev-active'), versions[0]);
		expect(s.open).toBeGreaterThan(0);
		expect(s.verdictKey).toBe('draft');
	});
});

describe('REVIEW_STATUS_META', () => {
	it('has an entry for every review status', () => {
		['draft', 'pending', 'approved', 'rejected'].forEach((k) => {
			expect(REVIEW_STATUS_META[k as keyof typeof REVIEW_STATUS_META]).toBeTruthy();
		});
	});
});
```

- [ ] **Step 2: Run it, confirm FAIL** (`Failed to resolve import './reviews'`)

Run: `npx vitest run src/lib/components/policy-review/lib/reviews.test.ts`

- [ ] **Step 3: Implement `reviews.ts`**
```ts
// Pure helpers for summarizing a Review for list/landing surfaces.

import type { ChecklistVersion, Review, ReviewStatus, VerdictKey } from './types';
import { computeScores } from './scoring';

export interface ReviewSummary {
	overall: number;
	verdictKey: VerdictKey;
	verdictLabel: string;
	gatesPass: boolean;
	open: number; // unresolved items (human + pending) blocking a final verdict
}

// Resolve the checklist version a review was assessed against (its snapshot),
// falling back to the active version, then the first known version.
export function versionFor(
	review: Review,
	versions: ChecklistVersion[]
): ChecklistVersion | undefined {
	return (
		versions.find((v) => v.id === review.checklistVersionId) ??
		versions.find((v) => v.status === 'active') ??
		versions[0]
	);
}

export function summarizeReview(review: Review, version: ChecklistVersion): ReviewSummary {
	const s = computeScores(version, review.results);
	const open = s.themeRows.reduce((a, t) => a + t.human + t.pending, 0);
	return {
		overall: s.overall,
		verdictKey: s.verdict.key,
		verdictLabel: s.verdict.label,
		gatesPass: s.gatesPass,
		open
	};
}

export const REVIEW_STATUS_META: Record<ReviewStatus, { label: string; tone: string }> = {
	draft: { label: 'Draft', tone: 'muted' },
	pending: { label: 'Pending approval', tone: 'info' },
	approved: { label: 'Approved', tone: 'ok' },
	rejected: { label: 'Returned', tone: 'bad' }
};
```

- [ ] **Step 4: Run tests, confirm PASS** (6 tests)

Run: `npx vitest run src/lib/components/policy-review/lib/reviews.test.ts`

- [ ] **Step 5: Commit**
```bash
git add src/lib/components/policy-review/lib/reviews.ts src/lib/components/policy-review/lib/reviews.test.ts
git commit -m "feat(policy-review): pure review-summary helper (score/verdict/open + version resolve)"
```

---

### Task 3: 6-view routing + role-gated redirects in `PolicyReviewApp.svelte`

**Files:**
- Modify: `src/lib/components/policy-review/PolicyReviewApp.svelte`

- [ ] **Step 1: Update the imports + the redirect guard**

Replace the store import line so it brings in the new view set and gates:
```ts
	import {
		view,
		stage,
		activeVersion,
		activeReview,
		drawerOpen,
		picked,
		canUseChecker,
		canApprove
	} from './lib/store';
```

Replace the existing single snap line
```ts
	$: if (!$canUseChecker && $view !== 'all-policies') view.set('all-policies');
```
with role-aware guards:
```ts
	// Snap users away from views their permissions don't allow, or a review view
	// with nothing selected. Library + Overview are open to everyone.
	$: if (($view === 'new-review' || $view === 'my-reviews') && !$canUseChecker) view.set('overview');
	$: if ($view === 'approvals' && !$canApprove) view.set('overview');
	$: if ($view === 'review' && !$activeReview) view.set('overview');
```

- [ ] **Step 2: Replace the view switch in the template**

Add the new view imports at the top of the script:
```ts
	import OverviewView from './views/OverviewView.svelte';
	import MyReviewsView from './views/MyReviewsView.svelte';
	import ApprovalQueueView from './views/ApprovalQueueView.svelte';
```
(keep the existing `AllPoliciesView`, `UploadView`, `ScanningView`, `ReviewView` imports).

Replace the `<div class="canvas"> ... </div>` body with:
```svelte
		<div class="canvas">
			{#if $view === 'overview'}
				<OverviewView />
			{:else if $view === 'library'}
				<AllPoliciesView />
			{:else if $view === 'my-reviews'}
				<MyReviewsView />
			{:else if $view === 'approvals'}
				<ApprovalQueueView />
			{:else if $view === 'new-review'}
				{#if $stage === 'upload'}
					<UploadView />
				{:else}
					<ScanningView />
				{/if}
			{:else}
				<ReviewView />
			{/if}
		</div>
```
(The `else` branch is `view === 'review'` → the shared review workspace.)

- [ ] **Step 3: Type-check**

Run: `npm run check` — the three new view imports will error ("Cannot find module") until Tasks 5–7 create them; that's expected. Confirm there are no OTHER new policy-review errors (e.g. the routing/guards themselves type-check). It's fine to commit after the views exist; if executing strictly task-by-task, do Step 4's commit after Tasks 5–7.

- [ ] **Step 4: Commit** (after the three view files exist, i.e. re-run this step's commit at the end of Task 7 if needed)
```bash
git add src/lib/components/policy-review/PolicyReviewApp.svelte
git commit -m "feat(policy-review): route 6 role-aware views with permission redirects"
```

---

### Task 4: Lean role-aware `ToolSidebar.svelte`

**Files:**
- Modify (replace): `src/lib/components/policy-review/chrome/ToolSidebar.svelte`

- [ ] **Step 1: Replace the component**

Replace the ENTIRE file with:
```svelte
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
```

- [ ] **Step 2: Type-check** — `npm run check`, confirm no new errors in `ToolSidebar.svelte`.

- [ ] **Step 3: Commit**
```bash
git add src/lib/components/policy-review/chrome/ToolSidebar.svelte
git commit -m "feat(policy-review): lean role-aware sidebar with live review/queue counts"
```

---

### Task 5: `OverviewView.svelte` (role-aware landing)

**Files:**
- Create: `src/lib/components/policy-review/views/OverviewView.svelte`

- [ ] **Step 1: Create the component**
```svelte
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
					<p class="ov-empty">No reviews in progress. Start one with “New review”.</p>
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
					<p class="ov-empty">Nothing in the queue. You’re all caught up.</p>
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
```

- [ ] **Step 2: Type-check** — `npm run check`, no new errors in `OverviewView.svelte`. (If `--ink-50` / `--surface` aren't defined the `var(..., fallback)` covers it; `color-mix` is supported by the target browsers — if `svelte-check`/build complains, replace the two `color-mix` lines with `background: var(--primary-50)` and a light gray.)

- [ ] **Step 3: Commit**
```bash
git add src/lib/components/policy-review/views/OverviewView.svelte
git commit -m "feat(policy-review): role-aware Overview landing"
```

---

### Task 6: `MyReviewsView.svelte`

**Files:**
- Create: `src/lib/components/policy-review/views/MyReviewsView.svelte`

- [ ] **Step 1: Create the component**
```svelte
<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import { myReviews, checklistVersions, openReview, goNewReview } from '../lib/store';
	import { summarizeReview, versionFor, REVIEW_STATUS_META } from '../lib/reviews';
	import type { Review } from '../lib/types';

	// Active work first (draft / returned), then pending, then decided.
	const ORDER: Record<Review['status'], number> = { rejected: 0, draft: 1, pending: 2, approved: 3 };
	let rows = $derived(
		[...$myReviews].sort((a, b) => ORDER[a.status] - ORDER[b.status])
	);

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
			<p>You haven’t started any reviews yet.</p>
			<button class="mr-btn primary" onclick={goNewReview} type="button">
				<Icon name="fileText" size={13} /> Start your first review
			</button>
		</div>
	{:else}
		<ul class="mr-list">
			{#each rows as r (r.id)}
				<li>
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
	.mr-row { display: flex; align-items: center; gap: 14px; width: 100%; text-align: left; background: none; border: 1px solid var(--ink-100); border-radius: 12px; padding: 13px 15px; cursor: pointer; color: inherit; }
	.mr-row:hover { border-color: var(--ink-200); }
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
```

- [ ] **Step 2: Type-check** — `npm run check`, no new errors in `MyReviewsView.svelte` (same `color-mix` fallback note as Task 5).

- [ ] **Step 3: Commit**
```bash
git add src/lib/components/policy-review/views/MyReviewsView.svelte
git commit -m "feat(policy-review): My reviews list with status + score"
```

---

### Task 7: `ApprovalQueueView.svelte`

**Files:**
- Create: `src/lib/components/policy-review/views/ApprovalQueueView.svelte`

- [ ] **Step 1: Create the component**
```svelte
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
			<p>No reviews awaiting approval. You’re all caught up.</p>
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
							<div class="aq-note">“{r.approval.note}”</div>
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
```

- [ ] **Step 2: Type-check** — `npm run check`; confirm the three new views + routing now produce ZERO policy-review errors. Fix any that remain.

- [ ] **Step 3: Commit** (this also satisfies Task 3 Step 4 if you deferred it)
```bash
git add src/lib/components/policy-review/views/ApprovalQueueView.svelte src/lib/components/policy-review/PolicyReviewApp.svelte
git commit -m "feat(policy-review): Approval queue view + finalize 6-view routing"
```

---

### Task 8: Wire lifecycle transitions + Plan 1 carry-overs

**Files:**
- Modify: `src/lib/components/policy-review/views/ScanningView.svelte`
- Modify: `src/lib/components/policy-review/views/AllPoliciesView.svelte`
- Modify: `src/lib/components/policy-review/chrome/Topbar.svelte`
- Modify: `src/lib/components/policy-review/views/ReviewView.svelte`
- Modify: `src/lib/components/policy-review/views/UploadView.svelte`

- [ ] **Step 1: Scanning completes into the review workspace**

In `ScanningView.svelte`, the `done()` function currently sets `stage.set('review')`. It must also route to the review view (so the wizard leaves `new-review`). Import `view` alongside `stage` and update:
```ts
	import { stage, view, activeVersion, activeReview } from '../lib/store';
	// ...
	function done() {
		stage.set('review');
		view.set('review');
	}
```

- [ ] **Step 2: Library reflects newly-approved reviews**

In `AllPoliciesView.svelte`, source the catalog from the `publishedPolicies` derived store (seeded library + any approved review) instead of the raw `POLICIES` import, so the approve→publish loop is visible. Change the import:
```ts
	import { FN_META, TODAY } from '../lib/seed';
	import { openPolicyPopup, publishedPolicies } from '../lib/store';
```
and replace the `const approvedAll = POLICIES.filter(...)` line with a reactive derivation:
```ts
	let approvedAll = $derived($publishedPolicies.filter((p) => p.status === 'approved'));
```
Then make the values that depend on `approvedAll` reactive: `filtered`, `groups`, `recent` already use `$derived` and keep working; convert `totalApproved` and `updatedThisMonth` from `const` to `$derived(...)`. Leave `totalFunctions = Object.keys(FN_META).length` as a `const` (it does not depend on `approvedAll`). Keep all markup unchanged.

- [ ] **Step 3: Topbar shows the active review (carry-over #1)**

In `Topbar.svelte`, replace the static `POLICY_META` import with the active review:
```ts
	import { activeReview } from '../lib/store';
	import { POLICY_META } from '../lib/seed';
	let meta = $derived($activeReview?.policyMeta ?? POLICY_META);
```
Replace `POLICY_META.<x>` references in the markup with `meta.<x>`.

- [ ] **Step 4: Submit-blocked copy counts all unresolved items (carry-over #2)**

In `ReviewView.svelte`, the side-rail message currently reads `Resolve {counts.human} human-review item…`. Replace the human-only count with all unresolved items (human + pending). Add a derived:
```ts
	let openCount = $derived((counts.human || 0) + (counts.pending || 0));
```
and change the message block to use `openCount` (and pluralize on `openCount`), and gate its `{#if}` on `openCount > 0` (or keep `scoreResult.humanItemsRemain`, which already covers human+pending). Update the wording to "Resolve {openCount} open item{…} before submitting for approval".

- [ ] **Step 5: UploadView shows the REAL active checklist (spec fix carried from Plan 1)**

`UploadView.svelte` still renders a fictional theme set (GOV/SCO/PRO/CTR/RSK/REV) in its "Validated against" preview. Drive it from the active checklist instead. Add the import and replace the hardcoded `themes`/`total` consts:
```ts
	import { stage, activeVersion } from '../lib/store';

	const HUES = [200, 30, 165, 0, 280, 130];
	let themes = $derived(
		($activeVersion?.themes ?? []).map((t, i) => ({
			id: t.id,
			name: t.name,
			count: ($activeVersion?.sections ?? [])
				.filter((s) => s.theme === t.id)
				.reduce((a, s) => a + s.items.length, 0),
			gate: t.gate,
			hue: HUES[i % HUES.length]
		}))
	);
	let total = $derived(themes.reduce((a, t) => a + t.count, 0));
```
All markup that reads `t.id`, `t.name`, `t.count`, `t.gate`, `t.hue`, `themes.length`, `themes.filter((t) => t.gate).length`, and `total` stays unchanged — it now reflects the real T1–T6 (6 themes, 70 items, 2 gates). Leave `start()` (`stage.set('scanning')`) as-is.

- [ ] **Step 6: Type-check + commit**

Run: `npm run check` — confirm zero policy-review errors.
```bash
git add src/lib/components/policy-review/views/ScanningView.svelte src/lib/components/policy-review/views/AllPoliciesView.svelte src/lib/components/policy-review/chrome/Topbar.svelte src/lib/components/policy-review/views/ReviewView.svelte src/lib/components/policy-review/views/UploadView.svelte
git commit -m "feat(policy-review): scan→review routing, real upload checklist, published-library, topbar+submit carry-overs"
```

---

### Task 9: Verification

**Files:** none (verification only)

- [ ] **Step 1: Full policy-review test suite**

Run: `npx vitest run src/lib/components/policy-review/`
Expected: PASS — `seed`, `checklist`, `scoring`, `store` (now 8 tests), `reviews` (6 tests), `library`, `roles`.

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: ZERO errors referencing `src/lib/components/policy-review/`.

- [ ] **Step 3: Boot smoke**

Start the dev server (`npm run dev`), then in the browser at `/policy-review` verify (logged in as / with permissions toggled):
- **Viewer** (no perms): sees Overview + Policy library only; no Reviewing/Approvals nav.
- **Reviewer** (`policy_checker`): Overview shows "My reviews" + New review; "My reviews" lists seeded reviews with status chips; New review runs upload → scan → lands in the review workspace; opening a returned review is editable; submit is blocked while items are open.
- **Approver** (`policy_approver`): "Approval queue" shows the two seeded pending reviews; opening one shows the read-only workspace with the approval banner; **Approve & publish** removes it from the queue and the policy appears as approved in the Library; **Reject** returns it.
- Admin (`role==='admin'`): sees all of the above (Admin page itself is Plan 3).

Stop the dev server when done.

- [ ] **Step 4: Commit any fixups discovered during smoke**
```bash
git add -A && git commit -m "fix(policy-review): smoke-test fixups for shell + lifecycle"
```
(skip if nothing needed)

---

## Self-review notes

- **Spec coverage:** §2 lean role-aware IA (Tasks 4 sidebar, 3 routing+gating); Overview landing (Task 5); My reviews (Task 6); Approval queue (Task 7); §3 lifecycle — submit→pending→approve/publish→library / reject→returned→edit reuses Plan-1 `ReviewView`/`ApprovalBanner` reached via `openReview` (Tasks 1, 6, 7) and the publish loop made visible (Task 8 Step 2). Admin entry/page deliberately excluded (Plan 3).
- **Plan 1 carry-overs addressed:** Topbar breadcrumb (Task 8 Step 3) and submit-blocked copy (Task 8 Step 4). Remaining carry-overs `myReviews` username-matching and `policyRoleLabel` admin case are noted below.
- **Type consistency:** `ViewKey` widened once (Task 1) and consumed in `PolicyReviewApp` (3), `ToolSidebar` (4), and nav helpers; `openReview(id)`/`goNewReview()` signatures match across store, sidebar, and all three list views; `summarizeReview(review, version)` + `versionFor(review, versions)` + `REVIEW_STATUS_META` used consistently in Overview/MyReviews/ApprovalQueue.
- **No placeholders:** every component is given in full; the only judgment calls flagged inline are the `color-mix` fallback and the deferred Task 3 commit.

### Carry-over into Plan 3
1. **`myReviews`** matches `createdBy === $user.name`; seeded reviews use fixed names so a real logged-in reviewer sees only `rev-active` (which is seeded to `'Ahmad Al-Sayegh'`). Plan 3 (or a Task here if desired) can reseed `rev-active.createdBy`/`goNewReview` to stamp the current `$user.name` so "My reviews" is populated for the demo account.
2. **`policyRoleLabel`** (`lib/roles.ts`) still has no Admin case — add it with the Admin entry in Plan 3.
3. **Admin** sidebar entry + page + `ViewKey` `'admin'` member land in Plan 3.
