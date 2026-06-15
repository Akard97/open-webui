# Policy Review finalization — Plan 3: Admin page + checklist versioning UI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `policy_admin`-gated Checklist Admin page — a four-tab editor (Checklist structure · Scoring & gates · Standards & codes · Access) that drives the draft → publish versioning lifecycle already built in Plan 1 — plus the Admin nav entry and two small carry-overs.

**Architecture:** The versioning engine exists and is tested (`lib/checklist.ts` `cloneAsDraft`/`validateDraft`/`publishDraft`; store `checklistDraft`/`startDraft`/`discardDraft`/`publishDraft`/`activeVersion`/`checklistVersions`/`canAdmin`). Plan 3 adds: a `standards` vocabulary to the checklist definition, `ViewKey 'admin'`, the Admin sidebar entry + route + gate, and the `AdminApp` shell with four tab components. `AdminApp` holds a deeply-reactive `$state` draft, the tabs mutate it in place (Svelte 5 deep reactivity), and Save/Publish persist via the existing store API. New reviews snapshot whatever version is active, so publishing a new version flows into the next review automatically — no extra wiring.

**Tech Stack:** SvelteKit, TypeScript, Svelte 5 runes (`$state`/`$derived`/`$props`, deep reactivity, `$state.snapshot`), Vitest 1.6, `svelte-check`.

**Spec:** `docs/superpowers/specs/2026-06-14-policy-review-finalization-design.md` (§5 admin page + versioning).
**Builds on:** Plan 1 (`...-1-foundation.md`) and Plan 2 (`...-2-shell-lifecycle.md`), both DONE.

**Conventions:**
- One test file: `npx vitest run <path>` · all: `npx vitest run src/lib/components/policy-review/`
- Type-check gate: `npm run check` → **no new errors under `src/lib/components/policy-review/`** (repo has ~300 unrelated pre-existing errors elsewhere).
- New components use a scoped `<style>` with existing CSS variables (`--ink-100..900`, `--primary`, `--primary-50`, `--ok`, `--bad`, `--warn`, `--mono`). The `color-mix(...)` fallback note from Plan 2 applies: if `svelte-check`/build rejects `color-mix`, swap for `var(--primary-50)` / a flat gray.
- The tabs mutate the shared `$state` draft **in place** (e.g. `draft.themes[i].weight = n`, `draft.sections.push(...)`, `draft.themes = draft.themes.filter(...)`). This is reactive in Svelte 5 because the draft is a `$state` proxy passed by reference — do NOT reassign the `draft` prop itself in a child (mutate its contents instead), so `$bindable` is not needed.

---

### Task 1: Add a `standards` vocabulary + `ViewKey 'admin'`

**Files:**
- Modify: `src/lib/components/policy-review/lib/types.ts`
- Modify: `src/lib/components/policy-review/lib/seed.ts`
- Modify: `src/lib/components/policy-review/lib/seed.test.ts`
- Modify: `src/lib/components/policy-review/lib/scoring.test.ts`
- Modify: `src/lib/components/policy-review/lib/store.ts`

> **Amendment (post-review fixes #1 & #3):**
> - **#3 — make `Theme.threshold` required.** In `types.ts` change `threshold?: number;` → `threshold: number; // gate threshold (default 85)`. In `seed.ts` `THEMES`, add `threshold: 85` to T3–T6 (only T1/T2 carry it today). In `scoring.test.ts` add `threshold: 85` to the T3–T6 entries of its `THEMES` literal. Behavior-preserving — `scoring.ts` reads `threshold` only for `gate` themes via `t.threshold || 85` — and it lets ScoringTab (Task 7) bind `<input type="number" bind:value={t.threshold}>` to a non-optional `number`; an optional `number | undefined` would fail `svelte-check` against the number-input `number | null` bind type.
> - **#1 — persist the admin view.** In `store.ts` `loadInitial()`, add `'admin'` to the whitelist array `['overview', 'library', 'new-review', 'my-reviews', 'approvals', 'review']` so a refresh while on the admin view restores it instead of bouncing to Overview.

- [ ] **Step 1: Types**

In `types.ts`, add the standard-code interface (place it next to `VerdictBands`):
```ts
export interface StandardCode {
	code: string; // e.g. 'OEC'
	label: string; // e.g. 'Organizational Excellence Checklist'
	description: string;
}
```
Add `standards` to `ChecklistVersion` (after `verdictBands`):
```ts
	verdictBands: VerdictBands;
	standards: StandardCode[];
```
And widen `ViewKey` to include admin:
```ts
export type ViewKey = 'overview' | 'library' | 'new-review' | 'my-reviews' | 'approvals' | 'review' | 'admin';
```

- [ ] **Step 2: Seed the vocabulary**

In `seed.ts`, add `StandardCode` to the type import from `./types`, then add the seed list above `buildActiveVersion` (after the `VERDICT_BANDS` const):
```ts
export const SEED_STANDARDS: StandardCode[] = [
	{ code: 'OEC', label: 'Organizational Excellence Checklist', description: 'Osool internal policy-quality checklist maintained by Organizational Excellence.' },
	{ code: 'ISO', label: 'ISO 9001:2015', description: 'International standard for quality management systems.' },
	{ code: 'OM', label: 'Osool Metapolicy', description: 'The governing policy-on-policies that defines how Osool policies are written and managed.' }
];
```
In `buildActiveVersion()`, add the `standards` field to the returned object:
```ts
		verdictBands: { ...VERDICT_BANDS },
		standards: structuredClone(SEED_STANDARDS)
```

- [ ] **Step 3: Extend the seed test**

In `seed.test.ts`, add to the `buildActiveVersion` describe block:
```ts
	it('seeds the standard-code vocabulary (OEC, ISO, OM)', () => {
		const v = buildActiveVersion();
		expect(v.standards.map((s) => s.code).sort()).toEqual(['ISO', 'OEC', 'OM']);
		expect(v.standards.every((s) => s.label && s.description)).toBe(true);
	});
```

- [ ] **Step 4: Run tests + type-check**

Run: `npx vitest run src/lib/components/policy-review/lib/seed.test.ts` → PASS.
Run: `npm run check` — `ChecklistVersion` now requires `standards`; any object literal building a `ChecklistVersion` without it will error. In source the only such literal is `buildActiveVersion` (fixed here). In tests, `scoring.test.ts` builds an inline `ChecklistVersion` via its `version()` helper — add `standards: []` to that literal. `reviews.test.ts` and `store.test.ts` obtain versions via `buildActiveVersion()`, so they need no change (but grep them for an inline `status: 'active'` literal just in case, and add `standards: []` if one exists). **Also (amendment #3):** `Theme.threshold` is now required, so add `threshold: 85` to the T3–T6 entries of the `THEMES` literal in `scoring.test.ts` (and confirm `seed.ts` `THEMES` got the same). The `store.ts` whitelist change (amendment #1) needs no test. Re-run `npx vitest run src/lib/components/policy-review/lib/` to confirm all green.

- [ ] **Step 5: Commit**
```bash
git add src/lib/components/policy-review/lib/types.ts src/lib/components/policy-review/lib/seed.ts src/lib/components/policy-review/lib/seed.test.ts src/lib/components/policy-review/lib/scoring.test.ts src/lib/components/policy-review/lib/store.ts
git commit -m "feat(policy-review): standards vocabulary + ViewKey 'admin' (+ required threshold, persist admin view)"
```
(If `reviews.test.ts`/`store.test.ts` did need a `standards: []`, include them in the `git add`.)

---

### Task 2: Draft-edit factories in `checklist.ts`

Pure factories so the admin "add" actions produce consistent, unique nodes — and are unit-tested.

**Files:**
- Modify: `src/lib/components/policy-review/lib/checklist.ts`
- Modify: `src/lib/components/policy-review/lib/checklist.test.ts`

- [ ] **Step 1: Write failing tests**

Append to `checklist.test.ts` (add `blankItem, blankSection, blankTheme, nextItemN` to the import from `./checklist`):
```ts
describe('draft-edit factories', () => {
	it('nextItemN returns one past the highest item number', () => {
		expect(nextItemN({ id: 'PRP1', theme: 'T1', title: 't', codes: 'c', intent: 'i', items: [
			{ id: 'PRP1-1', n: 1, text: 'a', codes: '', assessment: 'auto' },
			{ id: 'PRP1-4', n: 4, text: 'b', codes: '', assessment: 'auto' }
		] })).toBe(5);
		expect(nextItemN({ id: 'PRP9', theme: 'T1', title: 't', codes: 'c', intent: 'i', items: [] })).toBe(1);
	});

	it('blankItem builds a unique auto item id from section + number', () => {
		const it = blankItem('PRP1', 5);
		expect(it.id).toBe('PRP1-5');
		expect(it.n).toBe(5);
		expect(it.assessment).toBe('auto');
	});

	it('blankSection/blankTheme produce well-formed, empty-but-valid nodes', () => {
		const s = blankSection('T3', 'PRP99');
		expect(s.theme).toBe('T3');
		expect(s.id).toBe('PRP99');
		expect(s.items).toHaveLength(1); // starts with one blank item so it passes "no empty group"
		const t = blankTheme('T7');
		expect(t.id).toBe('T7');
		expect(t.weight).toBe(0);
		expect(t.gate).toBe(false);
	});
});
```

- [ ] **Step 2: Run → FAIL** (`nextItemN`/`blankItem`… not exported)

Run: `npx vitest run src/lib/components/policy-review/lib/checklist.test.ts`

- [ ] **Step 3: Implement the factories**

Append to `checklist.ts` (add `ChecklistItemDef`, `Section`, `Theme` to the type import):
```ts
export function nextItemN(section: Section): number {
	return section.items.reduce((max, it) => Math.max(max, it.n), 0) + 1;
}

export function blankItem(sectionId: string, n: number): ChecklistItemDef {
	return { id: `${sectionId}-${n}`, n, text: 'New requirement', codes: '', assessment: 'auto' };
}

export function blankSection(themeId: string, id: string): Section {
	return {
		id,
		theme: themeId,
		title: 'New PRP group',
		codes: '',
		intent: 'Describe what this group assesses.',
		items: [blankItem(id, 1)]
	};
}

export function blankTheme(id: string): Theme {
	return { id, name: 'New theme', weight: 0, gate: false, threshold: 85 };
}
```
(Update the import line at the top of `checklist.ts` to `import type { ChecklistVersion, ChecklistItemDef, Section, Theme } from './types';`.)

- [ ] **Step 4: Run → PASS** (10 tests total in the file)

Run: `npx vitest run src/lib/components/policy-review/lib/checklist.test.ts`

- [ ] **Step 5: Commit**
```bash
git add src/lib/components/policy-review/lib/checklist.ts src/lib/components/policy-review/lib/checklist.test.ts
git commit -m "feat(policy-review): draft-edit factories (blankItem/Section/Theme + nextItemN)"
```

---

### Task 3: Admin role label + `myReviews` author stamp (carry-overs)

**Files:**
- Modify: `src/lib/components/policy-review/lib/roles.ts`
- Modify: `src/lib/components/policy-review/lib/roles.test.ts`
- Modify: `src/lib/components/policy-review/lib/store.ts`
- Modify: `src/lib/components/policy-review/lib/store.test.ts`

- [ ] **Step 1: Add the admin case to `policyRoleLabel`**

Replace `roles.ts` body with the 3-arg version:
```ts
export function policyRoleLabel(
	canApprove: boolean,
	canUseChecker: boolean,
	canAdmin: boolean
): string {
	if (canApprove) return 'Organizational Excellence · Approver';
	if (canUseChecker) return 'Organizational Excellence · Reviewer';
	if (canAdmin) return 'Organizational Excellence · Admin';
	return 'Viewer';
}
```

- [ ] **Step 2: Update `roles.test.ts`**

Every existing `policyRoleLabel(a, b)` call needs a third arg. Add `false` to the existing calls, and add a case:
```ts
	it('labels an admin-only user as Admin', () => {
		expect(policyRoleLabel(false, false, true)).toBe('Organizational Excellence · Admin');
	});
	it('prefers Approver/Reviewer over Admin when combined', () => {
		expect(policyRoleLabel(true, false, true)).toBe('Organizational Excellence · Approver');
		expect(policyRoleLabel(false, true, true)).toBe('Organizational Excellence · Reviewer');
	});
```
(Read the file first; mechanically add the third argument to each pre-existing call.)

- [ ] **Step 3: Stamp the current user as author of new reviews**

In `store.ts`, update `resetReview()` so a freshly started review belongs to the current user (fixes "My reviews" reading empty for the demo account):
```ts
export function resetReview(): void {
	const seeded = buildSeedReviews();
	const me = get(user)?.name;
	const fresh = me ? { ...seeded[0], createdBy: me } : seeded[0];
	reviews.update((arr) => arr.map((r) => (r.id === 'rev-active' ? fresh : r)));
	activeReviewId.set('rev-active');
	stage.set('upload');
}
```

- [ ] **Step 4: Test the stamp**

Add to `store.test.ts` (the `user` store is the real `$lib/stores` writable; set it in the test):
```ts
import { user } from '$lib/stores';
import { resetReview } from './store';

describe('resetReview author stamp', () => {
	it('attributes the fresh review to the current user so it shows in My reviews', () => {
		user.set({ name: 'Test Reviewer', role: 'user', permissions: { features: {} } } as never);
		resetReview();
		const active = get(reviews).find((r) => r.id === 'rev-active')!;
		expect(active.createdBy).toBe('Test Reviewer');
		user.set(null as never);
	});
});
```
(If `user` is already imported in the file, merge the import. If setting `user` shape is awkward, cast via `as never` as shown — the test only reads `.name`.)

- [ ] **Step 5: Run + commit**

Run: `npx vitest run src/lib/components/policy-review/lib/roles.test.ts src/lib/components/policy-review/lib/store.test.ts` → PASS.
```bash
git add src/lib/components/policy-review/lib/roles.ts src/lib/components/policy-review/lib/roles.test.ts src/lib/components/policy-review/lib/store.ts src/lib/components/policy-review/lib/store.test.ts
git commit -m "feat(policy-review): Admin role label + stamp current user on new reviews"
```

---

### Task 4: Admin nav entry + route + gate

**Files:**
- Modify: `src/lib/components/policy-review/chrome/ToolSidebar.svelte`
- Modify: `src/lib/components/policy-review/PolicyReviewApp.svelte`

- [ ] **Step 1: Sidebar — add the Administration section**

In `ToolSidebar.svelte`:
- Add `canAdmin` to the store import.
- Widen the `go` signature: `function go(target: 'overview' | 'library' | 'my-reviews' | 'approvals' | 'admin')`.
- Update the footer label call to pass the third arg: `{policyRoleLabel($canApprove, $canUseChecker, $canAdmin)}`.
- Insert this block after the `{#if $canApprove}` Approvals section and before `<div class="sb-bottom">`:
```svelte
	{#if $canAdmin}
		<div class="sb-heading">Administration</div>
		<div class="sb-section" style="padding-top: 0">
			<button
				class="sb-link"
				class:active={$view === 'admin'}
				onclick={() => go('admin')}
				type="button"
			>
				<Icon name="sliders" size={15} /> Checklist admin
			</button>
		</div>
	{/if}
```
(`sliders` is an existing Icon name used elsewhere in the tool; if `npm run check`/render shows it missing, use `shield`.)

Also update the file's top comment — remove the "Admin entry is intentionally absent" note.

- [ ] **Step 2: App — route + gate the admin view**

In `PolicyReviewApp.svelte`:
- Add `AdminApp` import: `import AdminApp from './views/admin/AdminApp.svelte';`
- Add `canAdmin` to the store import.
- Add a gate alongside the others:
```ts
	$: if ($view === 'admin' && !$canAdmin) view.set('overview');
```
- Add the branch in the view switch (before the final `{:else}` ReviewView):
```svelte
				{:else if $view === 'admin'}
					<AdminApp />
```

- [ ] **Step 3: Type-check** — `npm run check`. The `AdminApp` import errors until Task 5 creates it; otherwise no new errors. Commit after Task 5 (or now and accept the transient missing-module until Task 5).

- [ ] **Step 4: Commit** (after Task 5 exists)
```bash
git add src/lib/components/policy-review/chrome/ToolSidebar.svelte src/lib/components/policy-review/PolicyReviewApp.svelte
git commit -m "feat(policy-review): Admin nav entry, route, and canAdmin gate"
```

---

### Task 5: `AdminApp.svelte` shell (tabs + save/publish/discard)

**Files:**
- Create: `src/lib/components/policy-review/views/admin/AdminApp.svelte`

- [ ] **Step 1: Create the shell**
```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import Icon from '../../ui/Icon.svelte';
	import {
		activeVersion,
		checklistDraft,
		publishDraft as storePublish,
		discardDraft
	} from '../../lib/store';
	import { cloneAsDraft, validateDraft } from '../../lib/checklist';
	import type { ChecklistVersion } from '../../lib/types';
	import ChecklistTab from './ChecklistTab.svelte';
	import ScoringTab from './ScoringTab.svelte';
	import StandardsTab from './StandardsTab.svelte';
	import AccessTab from './AccessTab.svelte';

	type Tab = 'checklist' | 'scoring' | 'standards' | 'access';
	let tab = $state<Tab>('checklist');

	// Deeply-reactive working copy. Resume an in-progress draft, else clone active.
	let draft = $state<ChecklistVersion>(
		structuredClone($checklistDraft ?? cloneAsDraft($activeVersion))
	);

	let errors = $state<string[]>([]);
	let toast = $state('');
	let live = $derived(validateDraft(draft));

	function flash(msg: string) {
		toast = msg;
		setTimeout(() => (toast = ''), 2500);
	}

	function save() {
		checklistDraft.set($state.snapshot(draft) as ChecklistVersion);
		errors = [];
		flash('Draft saved');
	}

	function publish() {
		const v = validateDraft(draft);
		if (!v.ok) {
			errors = v.errors;
			return;
		}
		checklistDraft.set($state.snapshot(draft) as ChecklistVersion);
		const res = storePublish();
		if (res.ok) {
			errors = [];
			draft = cloneAsDraft($activeVersion); // fresh draft off the freshly published version
			flash(`Published ${$activeVersion.label}`);
		} else {
			errors = res.errors;
		}
	}

	function discard() {
		discardDraft();
		draft = cloneAsDraft($activeVersion);
		errors = [];
		flash('Draft discarded');
	}

	const TABS: { id: Tab; label: string }[] = [
		{ id: 'checklist', label: 'Checklist' },
		{ id: 'scoring', label: 'Scoring & gates' },
		{ id: 'standards', label: 'Standards & codes' },
		{ id: 'access', label: 'Access' }
	];
</script>

<div class="adm">
	<header class="adm-head">
		<div>
			<div class="adm-eyebrow">Policy Review · Admin</div>
			<h1>Checklist administration</h1>
		</div>
		<div class="adm-actions">
			<span class="adm-ver">{$activeVersion.label} active · editing draft</span>
			<button class="adm-btn" onclick={discard} type="button">Discard</button>
			<button class="adm-btn" onclick={save} type="button">Save draft</button>
			<button class="adm-btn primary" onclick={publish} disabled={!live.ok} type="button">
				<Icon name="check" size={13} /> Publish
			</button>
		</div>
	</header>

	{#if toast}<div class="adm-toast">{toast}</div>{/if}

	{#if errors.length || !live.ok}
		<div class="adm-errors">
			<strong>Resolve before publishing:</strong>
			<ul>
				{#each (errors.length ? errors : live.errors) as e (e)}<li>{e}</li>{/each}
			</ul>
		</div>
	{/if}

	<nav class="adm-tabs">
		{#each TABS as t (t.id)}
			<button class="adm-tab" class:active={tab === t.id} onclick={() => (tab = t.id)} type="button">
				{t.label}
			</button>
		{/each}
	</nav>

	<div class="adm-body">
		{#if tab === 'checklist'}
			<ChecklistTab {draft} />
		{:else if tab === 'scoring'}
			<ScoringTab {draft} />
		{:else if tab === 'standards'}
			<StandardsTab {draft} />
		{:else}
			<AccessTab />
		{/if}
	</div>
</div>

<style>
	.adm { max-width: 1000px; margin: 0 auto; padding: 24px 24px 48px; }
	.adm-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
	.adm-eyebrow { font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-400); }
	.adm-head h1 { font-size: 22px; font-weight: 600; margin-top: 4px; }
	.adm-actions { display: flex; align-items: center; gap: 8px; }
	.adm-ver { font-size: 11.5px; color: var(--ink-500); margin-right: 4px; }
	.adm-btn { display: inline-flex; align-items: center; gap: 5px; font-size: 12.5px; padding: 7px 13px; border-radius: 9px; border: 1px solid var(--ink-200); background: none; cursor: pointer; }
	.adm-btn.primary { background: var(--primary); color: #fff; border-color: var(--primary); }
	.adm-btn:disabled { opacity: 0.5; cursor: not-allowed; }
	.adm-toast { margin-top: 12px; font-size: 12.5px; color: var(--ok); }
	.adm-errors { margin-top: 14px; border: 1px solid var(--bad); border-radius: 10px; padding: 10px 14px; font-size: 12.5px; color: var(--bad); }
	.adm-errors ul { margin: 6px 0 0; padding-left: 18px; }
	.adm-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--ink-100); margin: 18px 0 0; }
	.adm-tab { background: none; border: 0; border-bottom: 2px solid transparent; padding: 9px 12px; font-size: 13px; color: var(--ink-500); cursor: pointer; }
	.adm-tab.active { color: var(--ink-900); border-bottom-color: var(--primary); font-weight: 500; }
	.adm-body { padding-top: 18px; }
</style>
```

- [ ] **Step 2: Type-check** — the four tab imports error until Tasks 6–8 create them. Proceed; commit at the end of Task 8 (covers Task 4 Step 4 too).

---

### Task 6: `ChecklistTab.svelte` (structure editor)

**Files:**
- Modify: `src/lib/components/policy-review/ui/Icon.svelte` (add a `trash` icon)
- Create: `src/lib/components/policy-review/views/admin/ChecklistTab.svelte`

- [ ] **Step 1: Add a `trash` icon** (used by this tab and the Standards tab; the icon set currently has no `trash`)

In `ui/Icon.svelte`, add a new branch before the final `{/if}` (after the `folder` branch):
```svelte
	{:else if name === 'trash'}
		<polyline points="3 6 5 6 21 6" />
		<path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
		<path d="M10 11v6M14 11v6" />
		<path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2" />
	{/if}
```
(i.e. replace the trailing `{/if}` with the `{:else if name === 'trash'} … {/if}` shown.)

- [ ] **Step 2: Create the component**
```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import type { ChecklistVersion } from '../../lib/types';
	import { blankItem, blankSection, blankTheme, nextItemN } from '../../lib/checklist';

	let { draft }: { draft: ChecklistVersion } = $props();

	let open = $state<Record<string, boolean>>({});
	function toggle(id: string) { open = { ...open, [id]: !(open[id] ?? true) }; }
	function isOpen(id: string) { return open[id] ?? true; }

	function sectionsOf(themeId: string) {
		return draft.sections.filter((s) => s.theme === themeId);
	}
	function addItem(sectionId: string) {
		const sec = draft.sections.find((s) => s.id === sectionId);
		if (sec) sec.items.push(blankItem(sectionId, nextItemN(sec)));
	}
	function removeItem(sectionId: string, itemId: string) {
		const sec = draft.sections.find((s) => s.id === sectionId);
		if (sec) sec.items = sec.items.filter((i) => i.id !== itemId);
	}
	function addSection(themeId: string) {
		const id = `PRP${Date.now().toString().slice(-5)}`; // unique-enough id for a draft node
		draft.sections.push(blankSection(themeId, id));
	}
	function removeSection(sectionId: string) {
		draft.sections = draft.sections.filter((s) => s.id !== sectionId);
	}
	function addTheme() {
		// Amendment (fix #2): collision-proof id = one past the highest existing
		// T-number. A length-based id collides after a theme is removed (e.g. drop
		// T3 from T1–T6 → length 5 → "T6" duplicate), which crashes the keyed {#each}.
		const maxN = draft.themes.reduce((m, t) => {
			const n = Number(t.id.replace(/^T/, ''));
			return Number.isFinite(n) ? Math.max(m, n) : m;
		}, 0);
		draft.themes.push(blankTheme(`T${maxN + 1}`));
	}
	function removeTheme(themeId: string) {
		draft.themes = draft.themes.filter((t) => t.id !== themeId);
		draft.sections = draft.sections.filter((s) => s.theme !== themeId);
	}
</script>

<div class="ct">
	{#each draft.themes as theme (theme.id)}
		<div class="ct-theme">
			<div class="ct-theme-h">
				<button class="ct-chev" onclick={() => toggle(theme.id)} type="button">
					<Icon name={isOpen(theme.id) ? 'chevD' : 'chevR'} size={14} />
				</button>
				<span class="ct-tid">{theme.id}</span>
				<input class="ct-name" bind:value={theme.name} aria-label="Theme name" />
				{#if theme.gate}<span class="ct-gate">GATE</span>{/if}
				<span class="ct-meta">{theme.weight}% · {sectionsOf(theme.id).reduce((a, s) => a + s.items.length, 0)} items</span>
				<button class="ct-del" onclick={() => removeTheme(theme.id)} type="button" title="Remove theme">
					<Icon name="trash" size={13} />
				</button>
			</div>

			{#if isOpen(theme.id)}
				<div class="ct-sections">
					{#each sectionsOf(theme.id) as sec (sec.id)}
						<div class="ct-sec">
							<div class="ct-sec-h">
								<input class="ct-sec-title" bind:value={sec.title} aria-label="Group title" />
								<input class="ct-sec-codes" bind:value={sec.codes} placeholder="codes (e.g. ISO Cl.4.1 · OEC)" aria-label="Group codes" />
								<button class="ct-del" onclick={() => removeSection(sec.id)} type="button" title="Remove group">
									<Icon name="trash" size={13} />
								</button>
							</div>
							<input class="ct-sec-intent" bind:value={sec.intent} placeholder="What this group assesses" aria-label="Group intent" />

							<div class="ct-items">
								{#each sec.items as item (item.id)}
									<div class="ct-item">
										<span class="ct-itnum">{sec.id.replace('PRP', '')}.{item.n}</span>
										<textarea class="ct-ittext" bind:value={item.text} rows="1" aria-label="Requirement text"></textarea>
										<input class="ct-itcodes" bind:value={item.codes} placeholder="codes" aria-label="Item codes" />
										<div class="ct-assess">
											<button
												class="ct-seg"
												class:on={item.assessment === 'auto'}
												onclick={() => (item.assessment = 'auto')}
												type="button">Auto</button>
											<button
												class="ct-seg"
												class:on={item.assessment === 'human'}
												onclick={() => (item.assessment = 'human')}
												type="button">Human</button>
										</div>
										<button class="ct-del" onclick={() => removeItem(sec.id, item.id)} type="button" title="Remove item">
											<Icon name="x" size={13} />
										</button>
									</div>
								{/each}
								<button class="ct-add" onclick={() => addItem(sec.id)} type="button">
									<Icon name="plus" size={12} /> Add item
								</button>
							</div>
						</div>
					{/each}
					<button class="ct-add group" onclick={() => addSection(theme.id)} type="button">
						<Icon name="plus" size={12} /> Add PRP group
					</button>
				</div>
			{/if}
		</div>
	{/each}
	<button class="ct-add theme" onclick={addTheme} type="button">
		<Icon name="plus" size={12} /> Add theme
	</button>
</div>

<style>
	.ct { display: grid; gap: 12px; }
	.ct-theme { border: 1px solid var(--ink-100); border-radius: 12px; overflow: hidden; }
	.ct-theme-h { display: flex; align-items: center; gap: 8px; padding: 10px 12px; background: var(--ink-50, rgba(0,0,0,0.02)); }
	.ct-chev { background: none; border: 0; cursor: pointer; color: var(--ink-500); display: flex; }
	.ct-tid { font-family: var(--mono); font-size: 12px; color: var(--ink-500); }
	.ct-name { flex: 1; min-width: 0; font-size: 13.5px; font-weight: 500; border: 1px solid transparent; border-radius: 6px; padding: 3px 6px; background: none; }
	.ct-name:focus { border-color: var(--ink-200); background: #fff; outline: none; }
	.ct-gate { font-size: 10px; color: var(--bad); background: color-mix(in srgb, var(--bad) 12%, transparent); padding: 2px 6px; border-radius: 5px; }
	.ct-meta { font-size: 11.5px; color: var(--ink-400); }
	.ct-del { background: none; border: 0; color: var(--ink-400); cursor: pointer; display: flex; padding: 3px; }
	.ct-del:hover { color: var(--bad); }
	.ct-sections { padding: 10px 12px; display: grid; gap: 10px; }
	.ct-sec { border: 1px solid var(--ink-100); border-radius: 10px; padding: 10px; display: grid; gap: 7px; }
	.ct-sec-h { display: flex; gap: 8px; align-items: center; }
	.ct-sec-title { flex: 1; font-size: 12.5px; font-weight: 500; border: 1px solid var(--ink-100); border-radius: 6px; padding: 5px 7px; }
	.ct-sec-codes { width: 220px; font-size: 11.5px; font-family: var(--mono); border: 1px solid var(--ink-100); border-radius: 6px; padding: 5px 7px; }
	.ct-sec-intent { font-size: 12px; color: var(--ink-600); border: 1px solid var(--ink-100); border-radius: 6px; padding: 5px 7px; }
	.ct-items { display: grid; gap: 6px; }
	.ct-item { display: flex; gap: 8px; align-items: flex-start; }
	.ct-itnum { font-family: var(--mono); font-size: 11px; color: var(--ink-400); padding-top: 7px; min-width: 30px; }
	.ct-ittext { flex: 1; font-size: 12.5px; border: 1px solid var(--ink-100); border-radius: 6px; padding: 6px 8px; resize: vertical; font-family: inherit; }
	.ct-itcodes { width: 110px; font-size: 11px; font-family: var(--mono); border: 1px solid var(--ink-100); border-radius: 6px; padding: 6px 8px; }
	.ct-assess { display: flex; }
	.ct-seg { font-size: 11px; padding: 5px 9px; border: 1px solid var(--ink-200); background: none; cursor: pointer; }
	.ct-seg:first-child { border-radius: 6px 0 0 6px; }
	.ct-seg:last-child { border-radius: 0 6px 6px 0; border-left: 0; }
	.ct-seg.on { background: var(--primary); color: #fff; border-color: var(--primary); }
	.ct-add { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--primary); background: none; border: 1px dashed var(--ink-200); border-radius: 8px; padding: 6px 10px; cursor: pointer; justify-self: start; }
	.ct-add.theme { margin-top: 4px; }
</style>
```

- [ ] **Step 3: Type-check** — `npm run check`, no new errors in `Icon.svelte` or `ChecklistTab.svelte`.

---

### Task 7: `ScoringTab.svelte` (weights, gates, verdict bands)

**Files:**
- Create: `src/lib/components/policy-review/views/admin/ScoringTab.svelte`

> **Amendment note (fix #3):** `Theme.threshold` was made required in Task 1, so `bind:value={t.threshold}` below binds a non-optional `number` and passes `svelte-check`. No change to the component code shown.

- [ ] **Step 1: Create the component**
```svelte
<script lang="ts">
	import type { ChecklistVersion } from '../../lib/types';

	let { draft }: { draft: ChecklistVersion } = $props();

	let weightSum = $derived(draft.themes.reduce((a, t) => a + (Number(t.weight) || 0), 0));
</script>

<div class="sc">
	<section class="sc-card">
		<h2>Verdict thresholds</h2>
		<p class="sc-help">Weighted-score bands. Both mandatory gates must also pass for Approved / Conditional.</p>
		<div class="sc-bands">
			<label>Approved ≥
				<input type="number" min="0" max="100" bind:value={draft.verdictBands.approved} /> %
			</label>
			<label>Conditional ≥
				<input type="number" min="0" max="100" bind:value={draft.verdictBands.conditional} /> %
			</label>
			<span class="sc-note">Below {draft.verdictBands.conditional}% (or a failed gate) → Rejected.</span>
		</div>
	</section>

	<section class="sc-card">
		<div class="sc-card-h">
			<h2>Theme weights &amp; gates</h2>
			<span class="sc-sum" class:bad={Math.round(weightSum) !== 100}>Total {Math.round(weightSum)}% {Math.round(weightSum) === 100 ? '✓' : '(must be 100%)'}</span>
		</div>
		<div class="sc-rows">
			<div class="sc-row sc-head">
				<span>Theme</span><span>Weight %</span><span>Gate</span><span>Gate ≥</span>
			</div>
			{#each draft.themes as t (t.id)}
				<div class="sc-row">
					<span class="sc-name"><b>{t.id}</b> {t.name}</span>
					<input type="number" min="0" max="100" bind:value={t.weight} />
					<label class="sc-toggle"><input type="checkbox" bind:checked={t.gate} /> Mandatory</label>
					<input type="number" min="0" max="100" bind:value={t.threshold} disabled={!t.gate} />
				</div>
			{/each}
		</div>
	</section>
</div>

<style>
	.sc { display: grid; gap: 16px; }
	.sc-card { border: 1px solid var(--ink-100); border-radius: 12px; padding: 16px 18px; }
	.sc-card-h { display: flex; align-items: baseline; justify-content: space-between; }
	.sc-card h2 { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
	.sc-help { font-size: 12px; color: var(--ink-500); margin-bottom: 12px; }
	.sc-bands { display: flex; gap: 18px; align-items: center; flex-wrap: wrap; font-size: 13px; }
	.sc-bands input { width: 64px; }
	.sc-note { font-size: 12px; color: var(--ink-400); }
	.sc-sum { font-size: 12.5px; color: var(--ok); }
	.sc-sum.bad { color: var(--bad); }
	.sc-rows { display: grid; gap: 6px; margin-top: 10px; }
	.sc-row { display: grid; grid-template-columns: 1fr 90px 130px 90px; gap: 10px; align-items: center; font-size: 12.5px; }
	.sc-row.sc-head { font-size: 11px; color: var(--ink-400); text-transform: uppercase; letter-spacing: 0.04em; }
	.sc-name b { font-family: var(--mono); margin-right: 4px; }
	.sc-toggle { display: flex; align-items: center; gap: 6px; font-size: 12px; }
	.sc input[type='number'] { width: 80px; }
</style>
```

- [ ] **Step 2: Type-check** — `npm run check`, no new errors in `ScoringTab.svelte`.

---

### Task 8: `StandardsTab.svelte` + `AccessTab.svelte`

**Files:**
- Create: `src/lib/components/policy-review/views/admin/StandardsTab.svelte`
- Create: `src/lib/components/policy-review/views/admin/AccessTab.svelte`

- [ ] **Step 1: StandardsTab**
```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import type { ChecklistVersion } from '../../lib/types';

	let { draft }: { draft: ChecklistVersion } = $props();

	function add() {
		draft.standards.push({ code: 'NEW', label: 'New standard', description: '' });
	}
	function remove(i: number) {
		draft.standards = draft.standards.filter((_, idx) => idx !== i);
	}
</script>

<div class="st">
	<p class="st-help">
		The controlled vocabulary of standard codes that checklist items are tagged against
		(used in the Code column of the published checklist).
	</p>
	<div class="st-list">
		{#each draft.standards as s, i (i)}
			<div class="st-row">
				<input class="st-code" bind:value={s.code} aria-label="Code" />
				<div class="st-fields">
					<input class="st-label" bind:value={s.label} placeholder="Label" aria-label="Label" />
					<input class="st-desc" bind:value={s.description} placeholder="Description" aria-label="Description" />
				</div>
				<button class="st-del" onclick={() => remove(i)} type="button" title="Remove">
					<Icon name="trash" size={13} />
				</button>
			</div>
		{/each}
	</div>
	<button class="st-add" onclick={add} type="button"><Icon name="plus" size={12} /> Add standard</button>
</div>

<style>
	.st { display: grid; gap: 12px; }
	.st-help { font-size: 12.5px; color: var(--ink-500); }
	.st-list { display: grid; gap: 8px; }
	.st-row { display: flex; gap: 10px; align-items: flex-start; border: 1px solid var(--ink-100); border-radius: 10px; padding: 10px; }
	.st-code { width: 72px; font-family: var(--mono); font-size: 12.5px; font-weight: 500; border: 1px solid var(--ink-100); border-radius: 6px; padding: 6px 8px; }
	.st-fields { flex: 1; display: grid; gap: 6px; }
	.st-label { font-size: 12.5px; font-weight: 500; border: 1px solid var(--ink-100); border-radius: 6px; padding: 6px 8px; }
	.st-desc { font-size: 12px; color: var(--ink-600); border: 1px solid var(--ink-100); border-radius: 6px; padding: 6px 8px; }
	.st-del { background: none; border: 0; color: var(--ink-400); cursor: pointer; padding: 6px; }
	.st-del:hover { color: var(--bad); }
	.st-add { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--primary); background: none; border: 1px dashed var(--ink-200); border-radius: 8px; padding: 6px 10px; cursor: pointer; justify-self: start; }
</style>
```

- [ ] **Step 2: AccessTab** (read-only orientation + link to the real permission screen)
```svelte
<script lang="ts">
	const ROLES = [
		{ perm: 'policy_checker', name: 'Policy Checker (Reviewer)', desc: 'Upload, scan, review, and submit policies for approval.' },
		{ perm: 'policy_approver', name: 'Policy Approver', desc: 'Approve & publish or reject submitted reviews.' },
		{ perm: 'policy_admin', name: 'Policy Admin', desc: 'Manage this checklist, scoring, and standards.' }
	];
</script>

<div class="ax">
	<p class="ax-help">
		Access to the Policy Review tool is controlled by three group permissions. The policy
		library is open to everyone; the surfaces below are granted per group in the Admin Panel.
	</p>
	<div class="ax-cards">
		{#each ROLES as r (r.perm)}
			<div class="ax-card">
				<div class="ax-name">{r.name}</div>
				<code class="ax-perm">features.{r.perm}</code>
				<div class="ax-desc">{r.desc}</div>
			</div>
		{/each}
	</div>
	<a class="ax-link" href="/admin/users/groups">
		Manage groups &amp; permissions in the Admin Panel →
	</a>
	<p class="ax-note">System administrators always have all three.</p>
</div>

<style>
	.ax { display: grid; gap: 14px; }
	.ax-help { font-size: 12.5px; color: var(--ink-500); max-width: 70ch; }
	.ax-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
	.ax-card { border: 1px solid var(--ink-100); border-radius: 11px; padding: 13px 15px; }
	.ax-name { font-size: 13px; font-weight: 600; }
	.ax-perm { font-size: 11px; font-family: var(--mono); color: var(--primary); background: var(--primary-50); padding: 2px 6px; border-radius: 5px; display: inline-block; margin: 5px 0; }
	.ax-desc { font-size: 12px; color: var(--ink-600); }
	.ax-link { font-size: 13px; color: var(--primary); text-decoration: none; }
	.ax-note { font-size: 12px; color: var(--ink-400); }
</style>
```
(If `/admin/users/groups` 404s in this build, change the `href` to `/admin` — the Admin Panel root, which exists per `railItems.ts`.)

- [ ] **Step 3: Type-check + commit (covers Tasks 4–8)**

Run: `npm run check` — confirm ZERO errors under `src/lib/components/policy-review/`.
```bash
git add src/lib/components/policy-review/views/admin/ src/lib/components/policy-review/chrome/ToolSidebar.svelte src/lib/components/policy-review/PolicyReviewApp.svelte
git commit -m "feat(policy-review): admin page — checklist/scoring/standards/access tabs + draft→publish"
```

---

### Task 9: Verification

**Files:** none (verification only)

- [ ] **Step 1: Full test suite**

Run: `npx vitest run src/lib/components/policy-review/`
Expected: PASS — `seed` (+standards test), `checklist` (+factory tests), `scoring`, `store` (+author-stamp), `reviews`, `roles` (+admin label), `library`.

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: ZERO errors referencing `src/lib/components/policy-review/`.

- [ ] **Step 3: Boot smoke (admin journey)**

Start `npm run dev`, open `/policy-review` as an **admin** (or a user with `policy_admin`):
- "Checklist admin" appears in the sidebar under Administration; other roles don't see it.
- Open it → Checklist tab shows the 6 themes / PRP groups / 70 items; edit an item's text and toggle Auto/Human; add and remove an item.
- Scoring tab: the weight total reads 100% ✓; set a weight so the total ≠ 100 → the **Publish** button disables and the error banner explains why; restore to 100%.
- Standards tab: edit a label, add/remove a standard.
- Click **Publish** → version chip advances (v2.0 → v2.1). Then start a **New review** (as a reviewer/admin) and confirm the upload/scan/review reflect the edited checklist (e.g. the renamed item / new item appears), while any previously-open review is unchanged.
- Access tab: three permission cards + the Admin Panel link render.

Stop the dev server.

- [ ] **Step 4: Commit any smoke fixups** (skip if none)
```bash
git add -A && git commit -m "fix(policy-review): admin page smoke fixups"
```

---

## Self-review notes

- **Spec coverage (§5):** four tabs — Checklist structure (Task 6), Scoring & gates (Task 7), Standards & codes (Task 8 + the `standards` model in Task 1), Access summary (Task 8); draft→publish lifecycle reuses the Plan-1 store API via `AdminApp` (Task 5); snapshot-on-new-review needs no new wiring (new reviews already snapshot `activeVersion`); Admin nav entry + gate (Task 4). Carry-overs from Plan 2 closed: `policyRoleLabel` admin case + `myReviews` author stamp (Task 3).
- **Type consistency:** `ChecklistVersion` gains `standards: StandardCode[]` (Task 1) — every inline version literal in tests updated (`scoring.test`, `reviews.test`, and the test `buildActiveVersion` path). `policyRoleLabel` is 3-arg everywhere (roles.ts, roles.test, ToolSidebar). Tabs all receive `{ draft }: { draft: ChecklistVersion }` and mutate in place. `blankItem/blankSection/blankTheme/nextItemN` signatures match between `checklist.ts` and `ChecklistTab`.
- **No placeholders:** every component is given in full; flagged judgment calls are the `color-mix` fallback, the `sliders` icon fallback, and the `/admin/users/groups` href fallback.
- **Versioning safety:** `AdminApp` edits a `structuredClone` working copy; nothing touches `activeVersion`/`checklistVersions` until **Publish** validates and calls the tested `publishDraft`. In-flight reviews keep their snapshot. The Publish button is disabled while `validateDraft` fails (weights ≠ 100, empty theme/group), so an invalid checklist can't go live.

### Completes the finalization
With Plan 3 merged, all six views from the design exist, all four permissions are wired end-to-end, and the checklist is fully admin-managed with versioning — the clickable, backend-ready prototype is complete. The remaining work (real upload/parse, AI scan, multi-user persistence, endpoint enforcement, audit log, notifications) is the backend phase, explicitly out of scope for this frontend finalization.
