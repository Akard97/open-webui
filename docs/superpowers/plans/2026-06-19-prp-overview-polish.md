# Policy Review — Overview Page Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lift the Policy Review Overview page from "plain" to the same level of finish as the Library page, with zero behaviour change.

**Architecture:** Pure presentational change to a single Svelte 5 (runes) component, `OverviewView.svelte`. Add a brand accent strip, a mono eyebrow, a permission-gated stats band derived from stores already in the component, a two-column card row, section-accent dots, hover affordances, and function-colored accent bars on the published cards. All colors come from the existing `.pr-root` token palette (plus the brand olive `#769A4A` already used by `.pl-brand-line`). No new data, no new files, no other views touched.

**Tech Stack:** SvelteKit, Svelte 5 runes (`$derived`), scoped component CSS, design tokens defined in `src/lib/components/policy-review/styles.css`.

**Spec:** `docs/superpowers/specs/2026-06-19-prp-overview-polish-design.md`

**Note on testing:** This is a presentational component with no logic branches beyond existing permission gating. There is no unit test to write — verification is visual, via the preview harness (dev server render + snapshot/screenshot), plus confirming the dev server compiles with no console/HMR errors. The plan reflects that honestly rather than inventing a meaningless unit test.

---

## File Structure

- **Modify:** `src/lib/components/policy-review/views/OverviewView.svelte` — the only file changed. Both its `<script>` (add derived stats + a function-color map) and its markup + scoped `<style>` are replaced with the polished version below.
- **Read-only reference:** `src/lib/components/policy-review/styles.css` — source of the tokens (`--primary`, `--ink-*`, `--shadow-md`, `--mono`, `--primary-50`, `--primary-500`) and the brand gradient values reused below. Do not edit.

---

## Task 1: Replace OverviewView with the polished version

**Files:**
- Modify (full replace): `src/lib/components/policy-review/views/OverviewView.svelte`

- [ ] **Step 1: Confirm the current file is the expected baseline**

Run: open `src/lib/components/policy-review/views/OverviewView.svelte` and confirm it begins with `<script lang="ts">` importing from `../lib/store` and ends with the `.ov-rc-code` style rule. If it differs substantially from the spec's description, stop and re-read the spec before continuing.

- [ ] **Step 2: Replace the entire file contents**

Replace the whole file with exactly this content:

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
	let openMineAll = $derived(
		$myReviews.filter((r) => r.status === 'draft' || r.status === 'rejected')
	);
	let openMine = $derived(openMineAll.slice(0, 4));
	let pending = $derived($approvalQueue.slice(0, 4));
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
	const fnColor = (fn: string) => FN_COLOR[fn] ?? 'var(--ink-300)';

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
				<span class="em">Policy Review</span><span class="d"></span>Dashboard
			</div>
			<h1>Welcome back, {firstName}</h1>
			<p>Review policies against the PRP Master Checklist and publish approved policies to the library.</p>
			{#if stats.length}
				<div class="ov-stats">
					{#each stats as s, i (s.l)}
						{#if i > 0}<span class="ov-stats-sep">·</span>{/if}
						<div class="ov-stat"><b>{s.v}</b><span>{s.l}</span></div>
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
	.ov-stat:first-child b { color: var(--primary); }
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
```

- [ ] **Step 3: Verify the dev server compiles cleanly**

Start (or reuse) the dev server with the preview harness (`preview_start`). Then check `preview_console_logs` and `preview_logs`.
Expected: server compiles, no Svelte/Vite errors, no new console errors. If the project's dev server is not already running, the harness launches it; on this Windows box, see the project memory note about the vite/McAfee EPERM workaround if the server stalls on the splash.

---

## Task 2: Verify the polished page renders and still behaves identically

**Files:** none (verification only)

- [ ] **Step 1: Navigate to the Overview page**

Use `preview_eval` to navigate: `window.location.href = '/policy-review'` (the Overview is the default view). If the app requires sign-in, complete it the same way you normally verify this app, then ensure the Overview view is active.

- [ ] **Step 2: Snapshot the structure**

Run `preview_snapshot`.
Expected to see, in order: the eyebrow text "Policy Review · Dashboard", the "Welcome back, {firstName}" heading, the stats band (e.g. "in progress / awaiting you / published" depending on permissions), the "My reviews" and "Awaiting your approval" cards (subject to permissions), and the "Recently published" cards with codes like `OSOOL-RE-POL-...`.

- [ ] **Step 3: Confirm navigation still works (no behaviour change)**

Use `preview_click` on "Browse library" and confirm the Library view opens (`view` becomes `library`); navigate back to Overview. Repeat for "View all my reviews" → my-reviews and "Open approval queue" → approvals **only if** the current user has those permissions.
Expected: each link routes exactly as before this change.

- [ ] **Step 4: Confirm permission gating**

Reason about / verify the three gating outcomes:
- Checker + approver: stats band shows all three stats; both cards present.
- Library-only user (no checker, no approver): stats band shows only "published"; the `ov-row-cards` row is empty; "Recently published" still shows.
Expected: matches the spec's permission table. If you can switch users in the running app, verify the library-only case directly; otherwise confirm by reading the `{#if $canUseChecker}` / `{#if $canApprove}` guards and the `stats` derivation are intact.

- [ ] **Step 5: Check responsive collapse**

Run `preview_resize` to a narrow width (~700px) and `preview_snapshot`/`preview_screenshot`.
Expected: the "My reviews" / "Awaiting your approval" pair collapses from two columns to one (via `auto-fit, minmax(280px, 1fr)`); nothing overflows horizontally.

- [ ] **Step 6: Capture proof**

Run `preview_screenshot` at default width and save it as the visual proof of the finished page.
Expected: a screenshot showing the brand strip, eyebrow, stats band, accent-dotted card headers, and function-colored accent bars on the published cards.

---

## Task 3: Commit

**Files:**
- `src/lib/components/policy-review/views/OverviewView.svelte`

- [ ] **Step 1: Stage and commit**

```bash
git add src/lib/components/policy-review/views/OverviewView.svelte
git commit -m "feat(policy-review): polish Overview page to match Library finish

Brand accent strip, mono eyebrow, permission-gated stats band, two-column
card row, section-accent dots, hover affordances, and function-colored
accent bars on published cards. No behaviour change.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

Expected: one file changed, commit succeeds.

---

## Self-Review

**Spec coverage:**
- Brand accent strip → Task 1 (`.ov-brandline`). ✓
- Eyebrow → Task 1 (`.ov-eyebrow`). ✓
- Permission-gated stats band → Task 1 (`stats` derived + gating), Task 2 Step 4. ✓
- Card polish (accent dots, hover lift) → Task 1 (`.ov-dot`, `.ov-card:hover`). ✓
- Function-colored published cards → Task 1 (`FN_COLOR` + inline accent), Task 2 Step 6. ✓
- Empty states unchanged → Task 1 (`.ov-empty` messages verbatim). ✓
- Identical behaviour (copy, nav, gating, scoreOf) → Task 1 preserves all handlers; Task 2 Steps 3–4 verify. ✓
- Responsive collapse → Task 1 (`.ov-row-cards` auto-fit), Task 2 Step 5. ✓
- No raw hex outside palette → only `#003B4A` / `#0F5567` / `#769A4A`, all already in styles.css brand line. ✓

**Placeholder scan:** No TBD/TODO; all code shown in full. ✓

**Type/name consistency:** `openMineAll`/`openMine`/`pending`/`stats`/`publishedCount`/`fnColor`/`scoreOf` are defined once in the `<script>` and used consistently in markup. Store names (`canUseChecker`, `canApprove`, `myReviews`, `approvalQueue`, `checklistVersions`, `view`, `openReview`, `goNewReview`) match the existing imports. `r.policyMeta.name`, `r.createdBy`, `r.status`, `r.id`, `p.fn`, `p.title`, `p.code` all match the existing component's usage. ✓
