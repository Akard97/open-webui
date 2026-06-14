# Policy Review UI Honesty/Cleanup Pass — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove false/placeholder UI from the Policy Review tool (sidebar Recent/Archived lists, topbar sync badge) and replace the hardcoded "Organizational Excellence" identity label with an honest per-user role — with zero changes to workflow, stores, permissions, or backend.

**Architecture:** Three frontend Svelte components plus their shared stylesheet. The only behavioural logic (the footer role label) is extracted into a small pure function and unit-tested; the rest is markup/CSS deletion verified by the type checker, a build, and an orphan-reference grep.

**Tech Stack:** SvelteKit (Svelte 5 runes), TypeScript, Vitest, ESLint, `svelte-check`.

**Spec:** [docs/superpowers/specs/2026-06-14-policy-review-cleanup-design.md](../specs/2026-06-14-policy-review-cleanup-design.md)

---

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `src/lib/components/policy-review/lib/roles.ts` | Pure function deriving the sidebar footer identity label from permissions | **Create** |
| `src/lib/components/policy-review/lib/roles.test.ts` | Unit tests for `policyRoleLabel` | **Create** |
| `src/lib/components/policy-review/chrome/ToolSidebar.svelte` | Tool sidebar: remove Recent/Archived lists, wire honest footer label | **Modify** |
| `src/lib/components/policy-review/chrome/Topbar.svelte` | Top bar: remove the sync badge | **Modify** |
| `src/lib/components/policy-review/styles.css` | Remove orphaned `.sb-chat*`/`.pill*` and `.pl-topbar-sync` blocks; anchor footer to bottom | **Modify** |

Tasks are ordered so each ends in a coherent, self-contained commit.

---

## Task 1: Honest footer identity label (TDD)

Replace the inline footer logic that labels *every* user "Organizational Excellence" with a tested pure function: approvers/reviewers keep the OE department label, everyone else is a plain "Viewer".

**Files:**
- Create: `src/lib/components/policy-review/lib/roles.ts`
- Create: `src/lib/components/policy-review/lib/roles.test.ts`
- Modify: `src/lib/components/policy-review/chrome/ToolSidebar.svelte`

- [ ] **Step 1: Write the failing test**

Create `src/lib/components/policy-review/lib/roles.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { policyRoleLabel } from './roles';

describe('policyRoleLabel', () => {
	it('labels an approver as OE Approver (regardless of checker flag)', () => {
		expect(policyRoleLabel(true, true)).toBe('Organizational Excellence · Approver');
		expect(policyRoleLabel(true, false)).toBe('Organizational Excellence · Approver');
	});

	it('labels a checker-only user as OE Reviewer', () => {
		expect(policyRoleLabel(false, true)).toBe('Organizational Excellence · Reviewer');
	});

	it('labels a user with no policy permissions as a plain Viewer', () => {
		expect(policyRoleLabel(false, false)).toBe('Viewer');
	});
});
```

> Note: the separator is a middle dot `·` (U+00B7), matching the existing footer markup.

- [ ] **Step 2: Run the test to verify it fails**

Run: `npx vitest run src/lib/components/policy-review/lib/roles.test.ts`
Expected: FAIL — cannot resolve `./roles` (module does not exist yet).

- [ ] **Step 3: Write the minimal implementation**

Create `src/lib/components/policy-review/lib/roles.ts`:

```ts
// Derives the identity subtitle shown in the Policy Review sidebar footer.
// OE members (approvers/reviewers) are labelled with their Organizational
// Excellence role; everyone else is a plain library viewer. Pure function so
// the branching is unit-tested and the component template stays declarative.

export function policyRoleLabel(canApprove: boolean, canUseChecker: boolean): string {
	if (canApprove) return 'Organizational Excellence · Approver';
	if (canUseChecker) return 'Organizational Excellence · Reviewer';
	return 'Viewer';
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npx vitest run src/lib/components/policy-review/lib/roles.test.ts`
Expected: PASS — 3 passing.

- [ ] **Step 5: Wire the helper into the sidebar footer**

In `src/lib/components/policy-review/chrome/ToolSidebar.svelte`, add the import alongside the existing imports (just after the `store` import on line 11):

```svelte
	import { policyRoleLabel } from '../lib/roles';
```

Then replace the footer subtitle span. Find this block (near line 144):

```svelte
			<span style="font-size:11px; color:var(--ink-400)">
				Organizational Excellence{$canApprove ? ' · Approver' : $canUseChecker ? ' · Reviewer' : ''}
			</span>
```

Replace it with:

```svelte
			<span style="font-size:11px; color:var(--ink-400)">
				{policyRoleLabel($canApprove, $canUseChecker)}
			</span>
```

> `canApprove` and `canUseChecker` are already imported in this component (line 11) — no store import change needed.

- [ ] **Step 6: Verify the project type-checks**

Run: `npm run check`
Expected: completes with no new errors in `roles.ts` or `ToolSidebar.svelte`.

- [ ] **Step 7: Commit**

```bash
git add src/lib/components/policy-review/lib/roles.ts src/lib/components/policy-review/lib/roles.test.ts src/lib/components/policy-review/chrome/ToolSidebar.svelte
git commit -m "feat(policy-review): honest per-user sidebar identity label"
```

---

## Task 2: Remove sidebar Recent/Archived lists

Delete the hardcoded Recent reviews + Archived lists (markup, data arrays, helper) and their now-orphaned CSS. Because the removed list was the `flex: 1` element anchoring the footer to the bottom, add `margin-top: auto` to the foot-links so the footer stays pinned.

**Files:**
- Modify: `src/lib/components/policy-review/chrome/ToolSidebar.svelte`
- Modify: `src/lib/components/policy-review/styles.css`

- [ ] **Step 1: Remove the `recent`, `archived` arrays and `pillClass` helper**

In `src/lib/components/policy-review/chrome/ToolSidebar.svelte`, delete this entire block from the `<script>` (lines ~32–49):

```svelte
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
```

- [ ] **Step 2: Remove the Recent reviews + Archived markup**

In the same file, delete this entire block from the template (lines ~111–129):

```svelte
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
```

After this, the template flows directly from the `Workspace` `sb-section` into `<div class="sb-foot-links">`.

- [ ] **Step 3: Remove the orphaned sidebar CSS**

In `src/lib/components/policy-review/styles.css`, delete the `.sb-chat .pill` / `.pill-*` block (lines ~107–112):

```css
.sb-chat .pill { font-size: 10px; font-weight: 500; padding: 2px 7px; border-radius: 9px; letter-spacing: 0.01em; white-space: nowrap; }
.pill-inreview { background: oklch(0.94 0.04 75); color: oklch(0.45 0.08 60); }
.pill-approved { background: oklch(0.94 0.04 155); color: oklch(0.42 0.09 155); }
.pill-draft    { background: var(--ink-100); color: var(--ink-500); }
.pill-rejected { background: oklch(0.94 0.04 25);  color: oklch(0.45 0.12 25); }
.sb-chat.active .pill { background: white; color: var(--primary); }
```

Then delete the `.sb-chats` / `.sb-chat*` block (lines ~115–121). **Keep `.sb-heading` on line 114** — it still styles the "Workspace" heading:

```css
.sb-chats { padding: 0 10px; overflow-y: auto; flex: 1; }
.sb-chat { display: flex; align-items: center; gap: 9px; padding: 7px 10px; border-radius: 6px; color: var(--ink-700); cursor: pointer; white-space: nowrap; overflow: hidden; }
.sb-chat:hover { background: var(--ink-100); }
.sb-chat.active { background: var(--primary-50); color: var(--primary); font-weight: 500; }
.sb-chat .ico { font-size: 14px; }
.sb-chat .label { flex: 1; overflow: hidden; text-overflow: ellipsis; }
.sb-chat .meta { font-size: 11px; color: var(--ink-400); margin-left: 6px; }
```

- [ ] **Step 4: Re-anchor the footer to the bottom**

The removed `.sb-chats` had `flex: 1`, which pushed the foot-links and footer to the bottom of the column. Restore that by editing the `.sb-foot-links` rule (line ~105) from:

```css
.sb-foot-links { padding: 6px 10px; border-top: 1px solid var(--ink-100); }
```

to:

```css
.sb-foot-links { margin-top: auto; padding: 6px 10px; border-top: 1px solid var(--ink-100); }
```

- [ ] **Step 5: Verify no orphaned references remain**

Run: `npx rg "sb-chats|sb-chat|pillClass|\bpill\b|pill-" src/lib/components/policy-review`
Expected: no matches (all references removed across `.svelte` and `.css`).

- [ ] **Step 6: Verify the project type-checks**

Run: `npm run check`
Expected: completes with no new errors. (Svelte will flag unused `recent`/`archived`/`pillClass` if any were missed.)

- [ ] **Step 7: Commit**

```bash
git add src/lib/components/policy-review/chrome/ToolSidebar.svelte src/lib/components/policy-review/styles.css
git commit -m "refactor(policy-review): remove placeholder Recent/Archived sidebar lists"
```

---

## Task 3: Remove the topbar sync badge

Delete the "Synced 14m ago · Etimad · SharePoint · Drive" badge (it implies a live ingestion pipeline that doesn't exist), its backing constants, and its orphaned CSS.

**Files:**
- Modify: `src/lib/components/policy-review/chrome/Topbar.svelte`
- Modify: `src/lib/components/policy-review/styles.css`

- [ ] **Step 1: Remove the sync-state constants**

In `src/lib/components/policy-review/chrome/Topbar.svelte`, delete this block from the `<script>` (lines ~16–23):

```svelte
	// Mock — sync state. In a later phase this reads a real store backed by
	// the ingestion pipeline (sources: Etimad, SharePoint, Drive).
	const syncedMinutesAgo = 14;
	const stale = syncedMinutesAgo > 60 * 24;
	const syncLabel =
		syncedMinutesAgo < 60
			? `Synced ${syncedMinutesAgo}m ago`
			: `Synced ${Math.round(syncedMinutesAgo / 60)}h ago`;
```

- [ ] **Step 2: Remove the sync badge markup**

In the same file, delete this `<span>` from inside `<div class="tb-actions">` (lines ~43–52):

```svelte
		<span
			class="pl-topbar-sync"
			class:stale
			title={stale
				? 'Last sync over 24h ago — see runbook'
				: 'Sources: Etimad · SharePoint · Drive'}
		>
			<span class="dot" aria-hidden="true"></span>
			{syncLabel}
		</span>
```

After this, `tb-actions` contains only the existing `{#if $canUseChecker && $view === 'new-review' && $stage === 'review'}` button block — leave that untouched.

- [ ] **Step 3: Remove the orphaned topbar CSS**

In `src/lib/components/policy-review/styles.css`, delete the comment header and the `.pl-topbar-sync` blocks (lines ~1466–1491):

```css
/* ── Topbar sync badge ───────────────────────────────────────── */
.pl-topbar-sync {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px 5px 10px;
  border: 1px solid #E8F4ED;
  background: #F3F9F5;
  border-radius: 999px;
  font-size: 11.5px;
  color: var(--ok);
  font-family: var(--mono);
  letter-spacing: 0.02em;
}
.pl-topbar-sync .dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--ok);
  box-shadow: 0 0 0 4px rgba(31,122,77,.12);
}
.pl-topbar-sync.stale {
  border-color: #EDD9A4;
  background: var(--warn-50);
  color: var(--warn);
}
.pl-topbar-sync.stale .dot { background: var(--warn); box-shadow: 0 0 0 4px rgba(138,98,16,.12); }
```

Leave the following `/* Reduced motion */` block intact.

- [ ] **Step 4: Verify no orphaned references remain**

Run: `npx rg "pl-topbar-sync|syncLabel|syncedMinutesAgo" src/lib/components/policy-review`
Expected: no matches.

- [ ] **Step 5: Verify the project type-checks**

Run: `npm run check`
Expected: completes with no new errors. (Svelte will flag any leftover use of the removed `stale`/`syncLabel` bindings.)

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/policy-review/chrome/Topbar.svelte src/lib/components/policy-review/styles.css
git commit -m "refactor(policy-review): remove placeholder topbar sync badge"
```

---

## Task 4: Full verification

Confirm the whole pass holds together: tests, types, lint, build, and a manual smoke check of all three role variants.

**Files:** none (verification only).

- [ ] **Step 1: Run the policy-review unit tests**

Run: `npx vitest run src/lib/components/policy-review`
Expected: PASS — including the new `roles.test.ts` and the pre-existing `scoring`/`library` tests.

- [ ] **Step 2: Type-check the whole project**

Run: `npm run check`
Expected: no new errors introduced by this branch's changes.

- [ ] **Step 3: Lint the touched files**

Run: `npx eslint src/lib/components/policy-review/chrome/ToolSidebar.svelte src/lib/components/policy-review/chrome/Topbar.svelte src/lib/components/policy-review/lib/roles.ts`
Expected: no errors. (If ESLint auto-fixes formatting, re-stage and amend the relevant commit.)

- [ ] **Step 4: Production build**

Run: `npm run build`
Expected: build succeeds.

- [ ] **Step 5: Manual smoke (mock data)**

Start the dev server (`npm run dev`) and open `/policy-review`. Verify:
- Sidebar shows **no** Recent reviews / Archived section; the Workspace nav, foot-links (Templates / Audit log / Settings), and the user footer all render, with the footer pinned to the bottom of the sidebar.
- Topbar shows **no** "Synced … ago" badge; in the review stage a checker still sees the New review / Export buttons.
- Footer identity label, verified by toggling permissions (or admin vs plain user):
  - Approver (`features.policy_approver` or admin) → `Organizational Excellence · Approver`
  - Reviewer only (`features.policy_checker`) → `Organizational Excellence · Reviewer`
  - No permissions → `Viewer`

- [ ] **Step 6: Final confirmation**

No commit needed unless Step 3 produced lint fixes. The branch now contains three focused commits (footer label, sidebar lists, topbar badge) plus any lint amendment.

---

## Notes

- **Out of scope (do not touch):** the dead sidebar nav items (Search, Dashboard, In Review, Approvals, Compliance Checker, Exceptions, Templates, Audit log, Settings) and their counts (`142`/`7`/`3`); all upload/scan/review/approval workflow logic; the stores in `lib/store.ts`; permissions; backend.
- **No behaviour change:** a user performs the exact same actions with the exact same results before and after — only false/placeholder chrome is removed.
