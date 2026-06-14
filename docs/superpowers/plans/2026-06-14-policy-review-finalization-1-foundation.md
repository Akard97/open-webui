# Policy Review finalization — Plan 1: Foundation (permission + data model)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `policy_admin` permission and refactor the Policy Review tool's data layer to separate the *versioned checklist definition* from *per-review answers*, with all logic unit-tested, while keeping the existing 2-view app working.

**Architecture:** Two aggregate roots — `ChecklistVersion` (versioned definition: themes → PRP groups → items) and `Review` (policy + a snapshot `checklistVersionId` + `results` keyed by item id + lifecycle `status` + `approval`). The store holds `checklistVersions[]`, an editable `checklistDraft`, and `reviews[]`, with derived `activeVersion`, `activeReview`, `myReviews`, `approvalQueue`, and gates. Seeded mock data populates every future surface. This is the headless foundation; Plans 2 and 3 add UI on top.

**Tech Stack:** SvelteKit, TypeScript, Svelte stores, Vitest 1.6 (logic-level tests, colocated `*.test.ts`), `svelte-check`.

**Spec:** `docs/superpowers/specs/2026-06-14-policy-review-finalization-design.md` (§2 gate, §5 versioning, §6 data model).

**Conventions:**
- Run one test file: `npx vitest run <path>`
- Run all frontend tests: `npx vitest run`
- Type-check Svelte + TS: `npm run check`
- This plan keeps `ViewKey = 'all-policies' | 'new-review'` unchanged. The full 6-view IA is Plan 2.
- Item id convention: `itemId = "${sectionId}-${n}"` (e.g. `PRP1-3`). Selection state stays `{ sectionId, n }`; derive `itemId` where needed.

---

### Task 1: Backend — register `policy_admin` permission

**Files:**
- Modify: `backend/open_webui/config.py:1570-1572` (after `POLICY_APPROVER` env) and `:1648` (in `DEFAULT_USER_PERMISSIONS['features']`)

- [ ] **Step 1: Add the env-var flag**

After the `USER_PERMISSIONS_FEATURES_POLICY_APPROVER` block (ends line 1572), add:

```python
USER_PERMISSIONS_FEATURES_POLICY_ADMIN = (
    os.environ.get('USER_PERMISSIONS_FEATURES_POLICY_ADMIN', 'False').lower() == 'true'
)
```

- [ ] **Step 2: Add it to the default features map**

In `DEFAULT_USER_PERMISSIONS['features']`, immediately after the `'policy_approver': ...` line (1648), add:

```python
        'policy_admin': USER_PERMISSIONS_FEATURES_POLICY_ADMIN,
```

- [ ] **Step 3: Verify it imports cleanly**

Run: `python -c "import ast; ast.parse(open('backend/open_webui/config.py').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/open_webui/config.py
git commit -m "feat(policy-review): register policy_admin user permission (backend default)"
```

---

### Task 2: Frontend — add `policy_admin` to the default permissions constant

**Files:**
- Modify: `src/lib/constants/permissions.ts:68-69`

- [ ] **Step 1: Add the key**

In `DEFAULT_PERMISSIONS.features`, after `policy_approver: false,` (line 69), add:

```ts
		policy_admin: false
```

(Ensure the preceding `policy_approver: false` keeps/gets its trailing comma so the object stays valid.)

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: completes with no new errors referencing `permissions.ts`.

- [ ] **Step 3: Commit**

```bash
git add src/lib/constants/permissions.ts
git commit -m "feat(policy-review): add policy_admin to default frontend permissions"
```

---

### Task 3: Admin UI — "Policy Admin" group toggle

**Files:**
- Modify: `src/lib/components/admin/Users/Groups/Permissions.svelte` (after the Policy Approver block, which ends at line 998)

- [ ] **Step 1: Add the toggle block**

Immediately after the closing `</div>` of the Policy Approver block (line 998), insert a third block mirroring it exactly:

```svelte
		<div class="flex flex-col w-full">
			<Tooltip
				className="flex w-full justify-between my-1"
				content={$i18n.t(
					'Allows members of this group to manage the Policy Review checklist, scoring, and standards in the tool admin page.'
				)}
				placement="top-start"
			>
				<div class=" self-center text-xs font-medium">
					{$i18n.t('Policy Admin')}
				</div>
				<Switch bind:state={permissions.features.policy_admin} />
			</Tooltip>
			{#if defaultPermissions?.features?.policy_admin && !permissions.features.policy_admin}
				<div>
					<div class="text-xs text-gray-500">
						{$i18n.t('This is a default user permission and will remain enabled.')}
					</div>
				</div>
			{/if}
		</div>
```

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: no new errors referencing `Permissions.svelte`.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/admin/Users/Groups/Permissions.svelte
git commit -m "feat(policy-review): add Policy Admin group permission toggle"
```

---

### Task 4: New domain types (definition vs. review)

**Files:**
- Modify (replace contents): `src/lib/components/policy-review/lib/types.ts`

- [ ] **Step 1: Replace the file with the split model**

Replace the entire contents of `types.ts` with:

```ts
// Domain model for the Policy Review tool.
// Two aggregate roots: a versioned checklist DEFINITION, and per-policy REVIEWS
// that snapshot a checklist version and hold the answers.

// ─── Checklist definition (versioned) ──────────────────────────────────────

export type Assessment = 'auto' | 'human';

export interface ChecklistItemDef {
	id: string; // stable, e.g. 'PRP1-3'
	n: number; // display number within the PRP group
	text: string; // requirement text (no ' [H]' suffix)
	codes: string; // e.g. 'OEC, ISO'
	assessment: Assessment; // 'human' => routed to a person, AI leaves it blank
}

export interface Section {
	// A PRP group.
	id: string; // 'PRP1'..'PRP29'
	theme: string; // 'T1'..'T6'
	title: string;
	codes: string; // e.g. 'ISO Cl.4.1, 4.2 · OEC · OM'
	intent: string;
	items: ChecklistItemDef[];
}

export interface Theme {
	id: string; // 'T1'..'T6'
	name: string;
	weight: number; // percent
	gate: boolean;
	threshold?: number; // gate threshold, default 85
}

export interface VerdictBands {
	approved: number; // default 85
	conditional: number; // default 70
}

export type ChecklistStatus = 'active' | 'draft' | 'archived';

export interface ChecklistVersion {
	id: string; // 'v2.0'
	label: string; // 'v2.0'
	status: ChecklistStatus;
	publishedAt: string | null;
	publishedBy: string | null;
	changeSummary: string;
	themes: Theme[];
	sections: Section[];
	verdictBands: VerdictBands;
}

// ─── Review (per policy) ───────────────────────────────────────────────────

export type ItemVerdict = 'compliant' | 'non-compliant' | 'human' | 'pending';

export interface ItemResult {
	result: ItemVerdict;
	comment?: string;
	ref?: { section: string; quote: string } | null;
	confidence?: number;
	reviewed?: boolean;
	edited?: boolean;
}

export type ReviewStatus = 'draft' | 'pending' | 'approved' | 'rejected';

// Internal OE approval lifecycle (maker-checker). No external body.
export type ApprovalStatus = 'idle' | 'pending' | 'approved' | 'rejected';
export interface ApprovalState {
	status: ApprovalStatus;
	sentAt: string | null;
	decidedAt: string | null;
	decidedBy: string | null;
	note: string;
}

export interface PolicyMeta {
	name: string;
	code: string;
	version: string;
	owner: string;
	reviewer: string;
	reviewDate: string;
	pages: number;
	filename: string;
}

export interface Review {
	id: string;
	policyMeta: PolicyMeta;
	checklistVersionId: string; // snapshot taken when the review was created
	results: Record<string, ItemResult>; // keyed by ChecklistItemDef.id
	status: ReviewStatus;
	approval: ApprovalState;
	strengths: string[];
	createdBy: string;
	createdAt: string;
}

export type VerdictKey = 'draft' | 'approved' | 'conditional' | 'rejected';
export interface Verdict {
	key: VerdictKey;
	label: string;
	reason: string;
}

// ─── Library ────────────────────────────────────────────────────────────────

export type PolicyStatus =
	| 'approved'
	| 'in-review'
	| 'pending'
	| 'draft'
	| 'rejected'
	| 'expiring'
	| 'overdue';

export interface LibraryPolicy {
	code: string;
	title: string;
	fn: string;
	owner: string;
	version: string;
	status: PolicyStatus;
	score: number | null;
	pages: number;
	nextReview: string;
	updatedDays: number | null;
	current?: boolean;
	summary?: string | null;
	outline?: string[] | null;
	effectiveDate?: string | null;
	related?: string[];
}

// Transient view/stage keys (unchanged in Plan 1; expanded in Plan 2).
export type Stage = 'upload' | 'scanning' | 'review';
export type ViewKey = 'all-policies' | 'new-review';
```

- [ ] **Step 2: Type-check (expected to FAIL — consumers still use the old shape)**

Run: `npm run check`
Expected: errors in `mocks.ts`, `scoring.ts`, `store.ts`, `ReviewView.svelte` referencing removed `ChecklistItem`. This is expected; later tasks fix each consumer.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/policy-review/lib/types.ts
git commit -m "refactor(policy-review): split checklist definition from review answers in types"
```

---

### Task 5: Seed data + builders (`seed.ts`)

Keep the existing rich mock as `RAW_SECTIONS` (the only place results are written by hand) and *derive* the checklist definition and seeded reviews from it. This avoids re-transcribing 70 items.

**Files:**
- Rename: `src/lib/components/policy-review/lib/mocks.ts` → `src/lib/components/policy-review/lib/seed.ts`
- Test: `src/lib/components/policy-review/lib/seed.test.ts`

- [ ] **Step 1: Rename the data file and keep its arrays**

```bash
git mv src/lib/components/policy-review/lib/mocks.ts src/lib/components/policy-review/lib/seed.ts
```

In `seed.ts`:
1. Change the import line to add the new types:

```ts
import type {
	PolicyMeta,
	Theme,
	LibraryPolicy,
	PolicyStatus,
	ChecklistVersion,
	ChecklistItemDef,
	Section,
	Review,
	ItemResult,
	VerdictBands
} from './types';
```

2. Define a **raw** item shape local to this file (the hand-authored mock still carries results):

```ts
interface RawItem {
	n: number;
	text: string;
	code: string;
	result: ItemResult['result'];
	comment?: string;
	ref?: { section: string; quote: string } | null;
	confidence?: number;
}
interface RawSection {
	theme: string;
	id: string;
	title: string;
	codes: string;
	intent: string;
	items: RawItem[];
}
```

3. Rename the existing `export const SECTIONS: Section[]` literal to `const RAW_SECTIONS: RawSection[]` (same data, new name and type). Keep `THEMES`, `POLICY_META`, `FN_META`, `STATUS_META`, `POLICIES`, `STATUS_DIST`, `TOTAL_COUNT`, `FN_DIST`, `TODAY` exactly as they are.

- [ ] **Step 2: Add the verdict bands + builders**

Append to `seed.ts`:

```ts
export const VERDICT_BANDS: VerdictBands = { approved: 85, conditional: 70 };

export const ACTIVE_VERSION_ID = 'v2.0';

function defItem(raw: RawItem, sectionId: string): ChecklistItemDef {
	return {
		id: `${sectionId}-${raw.n}`,
		n: raw.n,
		text: raw.text.replace(' [H]', '').trim(),
		codes: raw.code,
		assessment: raw.result === 'human' ? 'human' : 'auto'
	};
}

function defSection(raw: RawSection): Section {
	return {
		id: raw.id,
		theme: raw.theme,
		title: raw.title,
		codes: raw.codes,
		intent: raw.intent,
		items: raw.items.map((it) => defItem(it, raw.id))
	};
}

// The active, published checklist definition (no answers).
export function buildActiveVersion(): ChecklistVersion {
	return {
		id: ACTIVE_VERSION_ID,
		label: 'v2.0',
		status: 'active',
		publishedAt: 'Jan 12, 2026',
		publishedBy: 'Organizational Excellence',
		changeSummary: 'PRP Master Checklist v2.0 — initial managed version.',
		themes: structuredClone(THEMES),
		sections: RAW_SECTIONS.map(defSection),
		verdictBands: { ...VERDICT_BANDS }
	};
}

// Answers for the rich in-progress review, keyed by item id.
function richResults(): Record<string, ItemResult> {
	const out: Record<string, ItemResult> = {};
	RAW_SECTIONS.forEach((sec) =>
		sec.items.forEach((it) => {
			out[`${sec.id}-${it.n}`] = {
				result: it.result,
				comment: it.comment,
				ref: it.ref ?? null,
				confidence: it.confidence
			};
		})
	);
	return out;
}

const RICH_STRENGTHS = [
	'Comprehensive RACI with explicit segregation of duties (§4)',
	'Strong escalation and approval flow with named final authority',
	'Complete dependency mapping in References (§11)'
];

// A library entry → a PolicyMeta for a seeded review.
function metaFor(code: string, reviewer: string): PolicyMeta {
	const p = POLICIES.find((x) => x.code === code)!;
	return {
		name: p.title,
		code: p.code,
		version: `v${p.version}`,
		owner: p.owner,
		reviewer,
		reviewDate: 'May 17, 2026',
		pages: p.pages,
		filename: `${p.title.replace(/\s+/g, '_')}_${p.version}.pdf`
	};
}

// Mutate a clone of the rich results so seeded extras have varied scores.
function tweak(results: Record<string, ItemResult>, flips: string[]): Record<string, ItemResult> {
	const clone = structuredClone(results);
	flips.forEach((id) => {
		if (clone[id]) clone[id] = { ...clone[id], result: 'non-compliant', comment: 'Seeded gap.' };
	});
	// Resolve any human items so seeded extras are submittable.
	Object.keys(clone).forEach((id) => {
		if (clone[id].result === 'human') clone[id] = { ...clone[id], result: 'compliant', reviewed: true };
	});
	return clone;
}

export function buildSeedReviews(): Review[] {
	const base = richResults();
	const submittable = tweak(base, []); // human items resolved, no extra flips
	return [
		{
			id: 'rev-active',
			policyMeta: POLICY_META,
			checklistVersionId: ACTIVE_VERSION_ID,
			results: base,
			status: 'draft',
			approval: { status: 'idle', sentAt: null, decidedAt: null, decidedBy: null, note: '' },
			strengths: RICH_STRENGTHS,
			createdBy: 'Ahmad Al-Sayegh',
			createdAt: 'May 17, 2026'
		},
		{
			id: 'rev-pending-1',
			policyMeta: metaFor('OSOOL-FIN-POL-002', 'Omar Al-Khalifa'),
			checklistVersionId: ACTIVE_VERSION_ID,
			results: submittable,
			status: 'pending',
			approval: { status: 'pending', sentAt: 'May 18, 09:20', decidedAt: null, decidedBy: null, note: 'Ready for issuance review.' },
			strengths: RICH_STRENGTHS,
			createdBy: 'Omar Al-Khalifa',
			createdAt: 'May 16, 2026'
		},
		{
			id: 'rev-pending-2',
			policyMeta: metaFor('OSOOL-IT-POL-005', 'Dalia Al-Ameri'),
			checklistVersionId: ACTIVE_VERSION_ID,
			results: tweak(base, ['PRP3-3', 'PRP8-4']),
			status: 'pending',
			approval: { status: 'pending', sentAt: 'May 18, 14:05', decidedAt: null, decidedBy: null, note: 'Two minor gaps flagged with CAP.' },
			strengths: RICH_STRENGTHS,
			createdBy: 'Dalia Al-Ameri',
			createdAt: 'May 15, 2026'
		},
		{
			id: 'rev-approved-1',
			policyMeta: metaFor('OSOOL-GOV-POL-014', 'Faisal Al-Jubeir'),
			checklistVersionId: ACTIVE_VERSION_ID,
			results: submittable,
			status: 'approved',
			approval: { status: 'approved', sentAt: 'May 10, 10:00', decidedAt: 'May 12, 11:30', decidedBy: 'Head of OE', note: 'Approved for issuance and published to the policy library.' },
			strengths: RICH_STRENGTHS,
			createdBy: 'Faisal Al-Jubeir',
			createdAt: 'May 08, 2026'
		},
		{
			id: 'rev-rejected-1',
			policyMeta: metaFor('OSOOL-HR-POL-005', 'Mohammed Al-Aqeel'),
			checklistVersionId: ACTIVE_VERSION_ID,
			results: tweak(base, ['PRP1-3', 'PRP6-7', 'PRP11-3', 'PRP11-4']),
			status: 'rejected',
			approval: { status: 'rejected', sentAt: 'May 11, 16:40', decidedAt: 'May 13, 09:15', decidedBy: 'Head of OE', note: 'Rejected — resolve the four governance gaps and resubmit.' },
			strengths: RICH_STRENGTHS,
			createdBy: 'Mohammed Al-Aqeel',
			createdAt: 'May 09, 2026'
		}
	];
}
```

- [ ] **Step 3: Write builder tests**

Create `seed.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { buildActiveVersion, buildSeedReviews, ACTIVE_VERSION_ID } from './seed';

describe('buildActiveVersion', () => {
	it('produces a definition with 6 themes and 70 items, no answers', () => {
		const v = buildActiveVersion();
		expect(v.id).toBe(ACTIVE_VERSION_ID);
		expect(v.themes).toHaveLength(6);
		const items = v.sections.flatMap((s) => s.items);
		expect(items).toHaveLength(70);
		// definition items carry no result field
		expect((items[0] as Record<string, unknown>).result).toBeUndefined();
	});

	it('flags [H] items as human assessment and strips the suffix', () => {
		const v = buildActiveVersion();
		const human = v.sections.flatMap((s) => s.items).filter((i) => i.assessment === 'human');
		expect(human.length).toBeGreaterThan(0);
		expect(human.every((i) => !i.text.includes('[H]'))).toBe(true);
	});

	it('gives every item a stable id of form PRP<x>-<n>', () => {
		const v = buildActiveVersion();
		const ids = v.sections.flatMap((s) => s.items.map((i) => i.id));
		expect(new Set(ids).size).toBe(ids.length);
		expect(ids.every((id) => /^PRP\d+-\d+$/.test(id))).toBe(true);
	});
});

describe('buildSeedReviews', () => {
	it('seeds one draft, two pending, one approved, one rejected', () => {
		const r = buildSeedReviews();
		const by = (s: string) => r.filter((x) => x.status === s).length;
		expect(by('draft')).toBe(1);
		expect(by('pending')).toBe(2);
		expect(by('approved')).toBe(1);
		expect(by('rejected')).toBe(1);
	});

	it('pending/approved reviews have no unresolved human items', () => {
		const r = buildSeedReviews().filter((x) => x.status === 'pending' || x.status === 'approved');
		r.forEach((rev) => {
			const human = Object.values(rev.results).filter((v) => v.result === 'human');
			expect(human).toHaveLength(0);
		});
	});
});
```

- [ ] **Step 4: Run the tests**

Run: `npx vitest run src/lib/components/policy-review/lib/seed.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/policy-review/lib/seed.ts src/lib/components/policy-review/lib/seed.test.ts
git commit -m "refactor(policy-review): derive versioned checklist + seeded reviews from raw mock"
```

---

### Task 6: Checklist versioning helpers (`checklist.ts`)

**Files:**
- Create: `src/lib/components/policy-review/lib/checklist.ts`
- Test: `src/lib/components/policy-review/lib/checklist.test.ts`

- [ ] **Step 1: Write the failing test**

Create `checklist.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { buildActiveVersion } from './seed';
import { cloneAsDraft, validateDraft, publishDraft, nextLabel } from './checklist';

describe('cloneAsDraft', () => {
	it('clones an active version into an editable draft with status draft', () => {
		const active = buildActiveVersion();
		const draft = cloneAsDraft(active);
		expect(draft.status).toBe('draft');
		expect(draft.sections).toHaveLength(active.sections.length);
		// deep clone — mutating the draft does not touch the source
		draft.sections[0].items[0].text = 'changed';
		expect(active.sections[0].items[0].text).not.toBe('changed');
	});
});

describe('validateDraft', () => {
	it('passes a well-formed draft', () => {
		const draft = cloneAsDraft(buildActiveVersion());
		expect(validateDraft(draft).ok).toBe(true);
	});

	it('fails when theme weights do not sum to 100', () => {
		const draft = cloneAsDraft(buildActiveVersion());
		draft.themes[0].weight += 5;
		const r = validateDraft(draft);
		expect(r.ok).toBe(false);
		expect(r.errors.join(' ')).toMatch(/100/);
	});

	it('fails when a theme has no items', () => {
		const draft = cloneAsDraft(buildActiveVersion());
		const emptyTheme = draft.themes[draft.themes.length - 1].id;
		draft.sections = draft.sections.filter((s) => s.theme !== emptyTheme);
		expect(validateDraft(draft).ok).toBe(false);
	});
});

describe('nextLabel', () => {
	it('bumps the minor version', () => {
		expect(nextLabel('v2.0')).toBe('v2.1');
		expect(nextLabel('v2.9')).toBe('v2.10');
	});
});

describe('publishDraft', () => {
	it('archives the old active and returns a new active version', () => {
		const active = buildActiveVersion();
		const draft = cloneAsDraft(active);
		const { versions, published } = publishDraft([active], draft, 'Head of OE');
		expect(published.status).toBe('active');
		expect(published.label).toBe('v2.1');
		expect(published.publishedBy).toBe('Head of OE');
		expect(versions.filter((v) => v.status === 'active')).toHaveLength(1);
		expect(versions.find((v) => v.id === active.id)!.status).toBe('archived');
	});
});
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `npx vitest run src/lib/components/policy-review/lib/checklist.test.ts`
Expected: FAIL ("Failed to resolve import './checklist'").

- [ ] **Step 3: Implement `checklist.ts`**

```ts
// Pure helpers for the checklist draft → publish lifecycle.
// No store/IO here — the store wires these in.

import type { ChecklistVersion } from './types';

export interface ValidationResult {
	ok: boolean;
	errors: string[];
}

export function cloneAsDraft(active: ChecklistVersion): ChecklistVersion {
	const draft = structuredClone(active);
	draft.status = 'draft';
	draft.publishedAt = null;
	draft.publishedBy = null;
	return draft;
}

export function validateDraft(draft: ChecklistVersion): ValidationResult {
	const errors: string[] = [];
	const weightSum = draft.themes.reduce((a, t) => a + (t.weight || 0), 0);
	if (Math.round(weightSum) !== 100) {
		errors.push(`Theme weights must sum to 100% (currently ${Math.round(weightSum)}%).`);
	}
	draft.themes.forEach((t) => {
		const secs = draft.sections.filter((s) => s.theme === t.id);
		if (secs.length === 0) {
			errors.push(`Theme ${t.id} has no PRP groups.`);
		}
		const itemCount = secs.reduce((a, s) => a + s.items.length, 0);
		if (itemCount === 0) {
			errors.push(`Theme ${t.id} has no items.`);
		}
	});
	draft.sections.forEach((s) => {
		if (s.items.length === 0) errors.push(`Group ${s.id} has no items.`);
	});
	return { ok: errors.length === 0, errors };
}

export function nextLabel(label: string): string {
	const m = label.match(/^v(\d+)\.(\d+)$/);
	if (!m) return `${label}.1`;
	return `v${m[1]}.${Number(m[2]) + 1}`;
}

export interface PublishResult {
	versions: ChecklistVersion[];
	published: ChecklistVersion;
}

// Archives every current active version and appends the draft as the new active.
// `now` is injectable so callers control timestamp formatting (and tests stay deterministic).
export function publishDraft(
	versions: ChecklistVersion[],
	draft: ChecklistVersion,
	publishedBy: string,
	now = 'now'
): PublishResult {
	const activeLabel = versions.find((v) => v.status === 'active')?.label ?? draft.label;
	const archived = versions.map((v) =>
		v.status === 'active' ? { ...v, status: 'archived' as const } : v
	);
	const published: ChecklistVersion = {
		...structuredClone(draft),
		label: nextLabel(activeLabel),
		id: nextLabel(activeLabel),
		status: 'active',
		publishedAt: now,
		publishedBy
	};
	return { versions: [...archived, published], published };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/lib/components/policy-review/lib/checklist.test.ts`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/policy-review/lib/checklist.ts src/lib/components/policy-review/lib/checklist.test.ts
git commit -m "feat(policy-review): checklist draft/validate/publish helpers"
```

---

### Task 7: Adapt scoring to `(version, results)`

**Files:**
- Modify: `src/lib/components/policy-review/lib/scoring.ts`
- Modify: `src/lib/components/policy-review/lib/scoring.test.ts`

- [ ] **Step 1: Rewrite the test for the new signature**

Replace the entire contents of `scoring.test.ts` with:

```ts
import { describe, it, expect } from 'vitest';
import { computeScores } from './scoring';
import type { ChecklistVersion, ItemResult, Theme } from './types';

const THEMES: Theme[] = [
	{ id: 'T1', name: 'Policy Foundation', weight: 28, gate: true, threshold: 85 },
	{ id: 'T2', name: 'Governance and Accountability', weight: 28, gate: true, threshold: 85 },
	{ id: 'T3', name: 'People and Communication', weight: 16, gate: false },
	{ id: 'T4', name: 'Performance and Measurement', weight: 14, gate: false },
	{ id: 'T5', name: 'Implementation and Change', weight: 7, gate: false },
	{ id: 'T6', name: 'Policy Integrity', weight: 7, gate: false }
];

const VERDICT_BANDS = { approved: 85, conditional: 70 };

// Build a one-item-per-theme version for the named themes.
function version(themeIds: string[]): ChecklistVersion {
	return {
		id: 'v',
		label: 'v',
		status: 'active',
		publishedAt: null,
		publishedBy: null,
		changeSummary: '',
		themes: THEMES,
		verdictBands: VERDICT_BANDS,
		sections: themeIds.map((t, i) => ({
			id: `PRP${i + 1}`,
			theme: t,
			title: 't',
			codes: 'c',
			intent: 'i',
			items: [{ id: `PRP${i + 1}-1`, n: 1, text: 't', codes: 'OEC', assessment: 'auto' as const }]
		}))
	};
}

const res = (pairs: Record<string, ItemResult['result']>): Record<string, ItemResult> =>
	Object.fromEntries(Object.entries(pairs).map(([k, v]) => [k, { result: v }]));

describe('computeScores', () => {
	it('marks Pending review when any human item is open', () => {
		const r = computeScores(version(['T1']), res({ 'PRP1-1': 'human' }));
		expect(r.verdict.key).toBe('draft');
		expect(r.humanItemsRemain).toBe(true);
	});

	it('marks Rejected when a gate theme fails', () => {
		const r = computeScores(version(['T1', 'T2']), res({ 'PRP1-1': 'non-compliant', 'PRP2-1': 'compliant' }));
		expect(r.verdict.key).toBe('rejected');
		expect(r.gatesPass).toBe(false);
	});

	it('marks Approved when overall ≥ 85 and gates pass', () => {
		const r = computeScores(version(['T1', 'T2', 'T3']), res({ 'PRP1-1': 'compliant', 'PRP2-1': 'compliant', 'PRP3-1': 'compliant' }));
		expect(r.overall).toBe(100);
		expect(r.verdict.key).toBe('approved');
	});

	it('treats a missing result as pending (excluded from score, blocks verdict)', () => {
		const r = computeScores(version(['T1']), res({}));
		expect(r.verdict.key).toBe('draft');
	});
});
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `npx vitest run src/lib/components/policy-review/lib/scoring.test.ts`
Expected: FAIL (computeScores still has the old signature).

- [ ] **Step 3: Rewrite `scoring.ts`**

Replace the entire contents with:

```ts
// Score + verdict calculation for the Policy Review tool.
//
// Per-theme score = compliant / (compliant + non-compliant).
// `human` and missing/`pending` items are held aside (not scored, but
// they block a final verdict). Gate themes must clear their threshold.
// Overall is the weight-weighted average of theme scores.

import type { ChecklistVersion, ItemResult, Theme, Verdict } from './types';

interface ThemeBucket {
	total: number;
	yes: number;
	no: number;
	human: number;
	pending: number;
	items: number;
}

export type ThemeRow = Theme & ThemeBucket & { pct: number };

export interface ScoreResult {
	themeRows: ThemeRow[];
	overall: number;
	gatesPass: boolean;
	verdict: Verdict;
	humanItemsRemain: boolean;
}

export function computeScores(
	version: ChecklistVersion,
	results: Record<string, ItemResult>
): ScoreResult {
	const { themes, sections, verdictBands } = version;
	const byTheme: Record<string, ThemeBucket> = {};
	themes.forEach((t) => {
		byTheme[t.id] = { total: 0, yes: 0, no: 0, human: 0, pending: 0, items: 0 };
	});

	sections.forEach((sec) => {
		const bucket = byTheme[sec.theme];
		if (!bucket) return;
		sec.items.forEach((item) => {
			bucket.items += 1;
			const result = results[item.id]?.result ?? 'pending';
			if (result === 'compliant') {
				bucket.yes += 1;
				bucket.total += 1;
			} else if (result === 'non-compliant') {
				bucket.no += 1;
				bucket.total += 1;
			} else if (result === 'human') {
				bucket.human += 1;
			} else {
				bucket.pending += 1;
			}
		});
	});

	const themeRows: ThemeRow[] = themes.map((t) => {
		const s = byTheme[t.id];
		const pct = s.total > 0 ? Math.round((s.yes / s.total) * 100) : 0;
		return { ...t, ...s, pct };
	});

	let weighted = 0;
	let weightTotal = 0;
	themeRows.forEach((t) => {
		if (t.total > 0) {
			weighted += t.pct * t.weight;
			weightTotal += t.weight;
		}
	});
	const overall = weightTotal > 0 ? Math.round(weighted / weightTotal) : 0;

	const gatesPass = themeRows.filter((t) => t.gate).every((t) => t.pct >= (t.threshold || 85));
	const humanItemsRemain = themeRows.some((t) => t.human > 0 || t.pending > 0);

	let verdict: Verdict;
	if (humanItemsRemain) {
		verdict = { key: 'draft', label: 'Pending review', reason: 'Awaiting unresolved items' };
	} else if (overall >= verdictBands.approved && gatesPass) {
		verdict = { key: 'approved', label: 'Approved', reason: 'Meets all requirements' };
	} else if (overall >= verdictBands.conditional && gatesPass) {
		verdict = {
			key: 'conditional',
			label: 'Conditionally Approved',
			reason: 'Minimum threshold met — CAP required'
		};
	} else {
		verdict = {
			key: 'rejected',
			label: 'Rejected',
			reason: gatesPass ? 'Below minimum overall threshold' : 'Mandatory gate failed'
		};
	}

	return { themeRows, overall, gatesPass, verdict, humanItemsRemain };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/lib/components/policy-review/lib/scoring.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/policy-review/lib/scoring.ts src/lib/components/policy-review/lib/scoring.test.ts
git commit -m "refactor(policy-review): score from (version, results) instead of result-bearing sections"
```

---

### Task 8: Rework the store (`store.ts`)

**Files:**
- Modify (replace contents): `src/lib/components/policy-review/lib/store.ts`
- Test: `src/lib/components/policy-review/lib/store.test.ts`

- [ ] **Step 1: Replace `store.ts`**

```ts
// Writable stores backing the Policy Review tool.
// Two aggregate roots: the versioned checklist definition and per-policy reviews.
// localStorage persistence keeps in-flight work across refreshes.

import { writable, get, derived, type Writable } from 'svelte/store';
import { browser } from '$app/environment';
import {
	buildActiveVersion,
	buildSeedReviews,
	POLICIES
} from './seed';
import { cloneAsDraft, publishDraft as publishDraftPure, validateDraft } from './checklist';
import type {
	ChecklistVersion,
	ItemResult,
	LibraryPolicy,
	Review,
	Stage,
	ViewKey
} from './types';
import { user } from '$lib/stores';

const STORAGE_KEY = 'osool.policyReview.v3';

interface PersistedState {
	versions: ChecklistVersion[];
	draft: ChecklistVersion | null;
	reviews: Review[];
	activeReviewId: string | null;
	stage: Stage;
	view: ViewKey;
}

function freshInitial(): PersistedState {
	const reviews = buildSeedReviews();
	return {
		versions: [buildActiveVersion()],
		draft: null,
		reviews,
		activeReviewId: reviews[0]?.id ?? null,
		stage: 'review',
		view: 'all-policies'
	};
}

function loadInitial(): PersistedState {
	if (!browser) return freshInitial();
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (raw) {
			const parsed = JSON.parse(raw) as Partial<PersistedState>;
			const fresh = freshInitial();
			return {
				versions: parsed.versions ?? fresh.versions,
				draft: parsed.draft ?? null,
				reviews: parsed.reviews ?? fresh.reviews,
				activeReviewId: parsed.activeReviewId ?? fresh.activeReviewId,
				stage: parsed.stage ?? 'review',
				view: parsed.view ?? 'all-policies'
			};
		}
	} catch {
		// Corrupt storage — fall back to fresh state.
	}
	return freshInitial();
}

const initial = loadInitial();

export const checklistVersions: Writable<ChecklistVersion[]> = writable(initial.versions);
export const checklistDraft: Writable<ChecklistVersion | null> = writable(initial.draft);
export const reviews: Writable<Review[]> = writable(initial.reviews);
export const activeReviewId: Writable<string | null> = writable(initial.activeReviewId);
export const stage: Writable<Stage> = writable(initial.stage);
export const view: Writable<ViewKey> = writable(initial.view);

// ─── Derived: checklist + reviews ──────────────────────────────────────────

export const activeVersion = derived(checklistVersions, ($v) => {
	return $v.find((x) => x.status === 'active') ?? $v[0];
});

export const activeReview = derived([reviews, activeReviewId], ([$r, $id]) =>
	$r.find((x) => x.id === $id) ?? null
);

export const approvalQueue = derived(reviews, ($r) => $r.filter((x) => x.status === 'pending'));

export const myReviews = derived([reviews, user], ([$r, $u]) =>
	$r.filter((x) => x.createdBy === ($u?.name ?? ''))
);

// Published canon = seeded library + any review that reached approved.
export const publishedPolicies = derived(reviews, ($r): LibraryPolicy[] => {
	const approvedCodes = new Set($r.filter((x) => x.status === 'approved').map((x) => x.policyMeta.code));
	const extra: LibraryPolicy[] = $r
		.filter((x) => x.status === 'approved' && !POLICIES.some((p) => p.code === x.policyMeta.code))
		.map((x) => ({
			code: x.policyMeta.code,
			title: x.policyMeta.name,
			fn: x.policyMeta.code.split('-')[1] ?? 'GOV',
			owner: x.policyMeta.owner,
			version: x.policyMeta.version.replace(/^v/, ''),
			status: 'approved',
			score: null,
			pages: x.policyMeta.pages,
			nextReview: '—',
			updatedDays: 0
		}));
	// Mark seeded entries that now have an approval as approved.
	const merged = POLICIES.map((p) =>
		approvedCodes.has(p.code) ? { ...p, status: 'approved' as const } : p
	);
	return [...merged, ...extra];
});

// ─── Access gates ──────────────────────────────────────────────────────────

export const canUseChecker = derived(
	user,
	($u) => $u?.role === 'admin' || ($u?.permissions?.features?.policy_checker ?? false)
);

export const canApprove = derived(
	user,
	($u) => $u?.role === 'admin' || ($u?.permissions?.features?.policy_approver ?? false)
);

export const canAdmin = derived(
	user,
	($u) => $u?.role === 'admin' || ($u?.permissions?.features?.policy_admin ?? false)
);

// ─── Transient UI (not persisted) ──────────────────────────────────────────

export const picked: Writable<{ sectionId: string; n: number } | null> = writable(null);
export const drawerOpen: Writable<boolean> = writable(false);
export const submitModalOpen: Writable<boolean> = writable(false);
export const policyPopupOpen: Writable<boolean> = writable(false);
export const selectedPolicy: Writable<LibraryPolicy | null> = writable(null);

if (browser) {
	const persist = () => {
		const snapshot: PersistedState = {
			versions: get(checklistVersions),
			draft: get(checklistDraft),
			reviews: get(reviews),
			activeReviewId: get(activeReviewId),
			stage: get(stage),
			view: get(view)
		};
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
		} catch {
			// Quota errors etc. are non-fatal.
		}
	};
	checklistVersions.subscribe(persist);
	checklistDraft.subscribe(persist);
	reviews.subscribe(persist);
	activeReviewId.subscribe(persist);
	stage.subscribe(persist);
	view.subscribe(persist);
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function stamp(): string {
	return new Date().toLocaleString('en-GB', {
		day: '2-digit',
		month: 'short',
		hour: '2-digit',
		minute: '2-digit'
	});
}

function patchReview(reviewId: string, fn: (r: Review) => Review): void {
	reviews.update((arr) => arr.map((r) => (r.id === reviewId ? fn(r) : r)));
}

// ─── Review mutators ─────────────────────────────────────────────────────────

export function updateItemResult(reviewId: string, itemId: string, patch: Partial<ItemResult>): void {
	patchReview(reviewId, (r) => ({
		...r,
		results: {
			...r.results,
			[itemId]: { ...(r.results[itemId] ?? { result: 'pending' }), ...patch }
		}
	}));
}

export function markReviewed(reviewId: string, itemId: string): void {
	updateItemResult(reviewId, itemId, { reviewed: true, confidence: 0.99 });
}

// Reset the active review back to a fresh draft of the seeded "active" review.
// (Plan 2 replaces this with real createReview() from an upload.)
export function resetReview(): void {
	const seeded = buildSeedReviews();
	reviews.update((arr) => arr.map((r) => (r.id === 'rev-active' ? seeded[0] : r)));
	activeReviewId.set('rev-active');
	stage.set('upload');
}

export function submitForApproval(reviewId: string, note: string): void {
	patchReview(reviewId, (r) => ({
		...r,
		status: 'pending',
		approval: { status: 'pending', sentAt: stamp(), decidedAt: null, decidedBy: null, note }
	}));
}

const DEFAULT_APPROVE_NOTE = 'Approved for issuance and published to the policy library.';
const DEFAULT_REJECT_NOTE =
	'Rejected — policy must be revised and re-reviewed before it can be resubmitted.';

export function approveAndPublish(reviewId: string, note?: string): void {
	const by = get(user)?.name ?? 'OE Approver';
	patchReview(reviewId, (r) => ({
		...r,
		status: 'approved',
		approval: {
			...r.approval,
			status: 'approved',
			decidedAt: stamp(),
			decidedBy: by,
			note: note?.trim() || DEFAULT_APPROVE_NOTE
		}
	}));
}

export function rejectPolicy(reviewId: string, note?: string): void {
	const by = get(user)?.name ?? 'OE Approver';
	patchReview(reviewId, (r) => ({
		...r,
		status: 'rejected',
		approval: {
			...r.approval,
			status: 'rejected',
			decidedAt: stamp(),
			decidedBy: by,
			note: note?.trim() || DEFAULT_REJECT_NOTE
		}
	}));
}

// ─── Checklist draft mutators (UI lands in Plan 3) ──────────────────────────

export function startDraft(): void {
	const active = get(activeVersion);
	if (active) checklistDraft.set(cloneAsDraft(active));
}

export function discardDraft(): void {
	checklistDraft.set(null);
}

export function publishDraft(): { ok: boolean; errors: string[] } {
	const draft = get(checklistDraft);
	if (!draft) return { ok: false, errors: ['No draft to publish.'] };
	const validation = validateDraft(draft);
	if (!validation.ok) return validation;
	const by = get(user)?.name ?? 'Policy Admin';
	const { versions } = publishDraftPure(get(checklistVersions), draft, by, stamp());
	checklistVersions.set(versions);
	checklistDraft.set(null);
	return { ok: true, errors: [] };
}

// ─── Policy Library popup helpers ──────────────────────────────────────────

export function openPolicyPopup(policy: LibraryPolicy): void {
	selectedPolicy.set(policy);
	policyPopupOpen.set(true);
}

export function closePolicyPopup(): void {
	policyPopupOpen.set(false);
}
```

- [ ] **Step 2: Write the failing test**

Create `store.test.ts`:

```ts
import { describe, it, expect, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import {
	reviews,
	activeReviewId,
	activeReview,
	approvalQueue,
	updateItemResult,
	submitForApproval,
	approveAndPublish,
	rejectPolicy,
	startDraft,
	publishDraft,
	checklistVersions,
	checklistDraft
} from './store';
import { buildSeedReviews, buildActiveVersion } from './seed';

beforeEach(() => {
	reviews.set(buildSeedReviews());
	activeReviewId.set('rev-active');
	checklistVersions.set([]);
	checklistDraft.set(null);
});

describe('review mutators', () => {
	it('updateItemResult patches a single item result', () => {
		updateItemResult('rev-active', 'PRP1-1', { result: 'non-compliant', edited: true });
		expect(get(activeReview)!.results['PRP1-1'].result).toBe('non-compliant');
		expect(get(activeReview)!.results['PRP1-1'].edited).toBe(true);
	});

	it('submitForApproval moves a review into the queue as pending', () => {
		submitForApproval('rev-active', 'please review');
		expect(get(activeReview)!.status).toBe('pending');
		expect(get(approvalQueue).some((r) => r.id === 'rev-active')).toBe(true);
	});

	it('approveAndPublish marks approved and records a decider', () => {
		submitForApproval('rev-active', 'x');
		approveAndPublish('rev-active', 'looks good');
		const r = get(reviews).find((x) => x.id === 'rev-active')!;
		expect(r.status).toBe('approved');
		expect(r.approval.decidedBy).toBeTruthy();
	});

	it('rejectPolicy marks rejected with a note', () => {
		submitForApproval('rev-active', 'x');
		rejectPolicy('rev-active', 'fix gaps');
		expect(get(reviews).find((x) => x.id === 'rev-active')!.status).toBe('rejected');
	});
});

describe('checklist draft lifecycle', () => {
	it('publishDraft fails validation when weights are off', () => {
		checklistVersions.set([buildActiveVersion()]);
		startDraft();
		const d = get(checklistDraft)!;
		d.themes[0].weight += 10;
		checklistDraft.set(d);
		const r = publishDraft();
		expect(r.ok).toBe(false);
	});

	it('publishDraft appends a new active version on success', () => {
		checklistVersions.set([buildActiveVersion()]);
		startDraft();
		const r = publishDraft();
		expect(r.ok).toBe(true);
		const actives = get(checklistVersions).filter((v) => v.status === 'active');
		expect(actives).toHaveLength(1);
		expect(actives[0].label).toBe('v2.1');
	});
});
```

- [ ] **Step 3: Run it**

Run: `npx vitest run src/lib/components/policy-review/lib/store.test.ts`
Expected: PASS (6 tests).

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/policy-review/lib/store.ts src/lib/components/policy-review/lib/store.test.ts
git commit -m "refactor(policy-review): store around checklist versions + reviews collection"
```

---

### Task 9: Adapt the review workspace (`ReviewView.svelte`)

The workspace must read the active review's answers against its checklist-version snapshot instead of a global `sections` array.

**Files:**
- Modify: `src/lib/components/policy-review/views/ReviewView.svelte`

- [ ] **Step 1: Update imports + derived data**

Replace the import of `THEMES, POLICY_META` and the `sections`/`approval` store imports. New script-top wiring:

```ts
	import { computeScores } from '../lib/scoring';
	import type { Section, ChecklistItemDef, ItemResult } from '../lib/types';
	import {
		activeReview,
		activeVersion,
		picked,
		drawerOpen,
		submitModalOpen,
		canUseChecker,
		updateItemResult
	} from '../lib/store';

	type Filter = 'all' | 'issues' | 'human' | 'compliant';
	let openMap = $state<Record<string, boolean>>({});
	let filter = $state<Filter>('all');

	function setOpen(id: string, v: boolean) {
		openMap = { ...openMap, [id]: v };
	}

	// The checklist version this review was assessed against. In Plan 1 there is
	// only the active version; Plan 2 resolves it by $activeReview.checklistVersionId.
	let version = $derived($activeVersion);
	let sectionsList = $derived(version?.sections ?? []);
	let themesList = $derived(version?.themes ?? []);
	let results = $derived($activeReview?.results ?? {});
	let meta = $derived($activeReview?.policyMeta);
	let approval = $derived($activeReview?.approval);
	let strengths = $derived($activeReview?.strengths ?? []);
	let locked = $derived($activeReview ? $activeReview.status !== 'draft' && $activeReview.status !== 'rejected' : false);

	function rOf(sec: Section, it: ChecklistItemDef): ItemResult {
		return results[it.id] ?? { result: 'pending' };
	}

	let scoreResult = $derived(
		version ? computeScores(version, results) : null
	);
```

- [ ] **Step 2: Replace `$sections` usages throughout the markup**

Mechanical replacements across this component:
- `THEMES` → `themesList`; `$sections` → `sectionsList`.
- Every read of `it.result` → `rOf(sec, it).result`; `it.confidence` → `rOf(sec, it).confidence`; `it.reviewed`/`it.edited`/`it.comment` likewise via `rOf(sec, it)`.
- `POLICY_META.<x>` → `meta?.<x>`.
- `$approval` → `approval`; guard the banner with `{#if approval && approval.status !== 'idle'}`.
- `scoreResult.*` reads must guard for null: wrap the side-rail + verdict in `{#if scoreResult}`.
- `counts`, `totalItems`, `topGaps`, `byTheme`, `sectionCounts`, `sectionVisibleItems`, `themeHasVisible` must iterate `sectionsList` and use `rOf(...)` for the result. Replace the hardcoded `strengths` const with the `strengths` derived.
- Item key/number: `item-num` becomes `{sec.id.replace('PRP','')}.{it.n}`; pass `it.id` where a stable key is needed.
- The submit button's `disabled` becomes `disabled={!scoreResult || scoreResult.humanItemsRemain || locked || approval?.status === 'pending'}` and is wrapped in `{#if $canUseChecker && !locked}`.

- [ ] **Step 3: Type-check**

Run: `npm run check`
Expected: no errors in `ReviewView.svelte`. Fix any residual `it.result`/`THEMES`/`POLICY_META` references the check reports.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/policy-review/views/ReviewView.svelte
git commit -m "refactor(policy-review): review workspace reads active review + version snapshot"
```

---

### Task 10: Adapt overlays + app shell to the per-review model

**Files:**
- Modify: `src/lib/components/policy-review/views/ItemDrawer.svelte`
- Modify: `src/lib/components/policy-review/views/SubmitApprovalModal.svelte`
- Modify: `src/lib/components/policy-review/views/ApprovalBanner.svelte`
- Modify: `src/lib/components/policy-review/views/ScanningView.svelte`
- Modify: `src/lib/components/policy-review/views/AllPoliciesView.svelte`
- Modify: `src/lib/components/policy-review/views/PolicyPopup.svelte`
- Modify: `src/lib/components/policy-review/chrome/Topbar.svelte`
- Modify: `src/lib/components/policy-review/PolicyReviewApp.svelte`
- Modify: `src/lib/components/policy-review/chrome/ToolSidebar.svelte`

- [ ] **Step 1: ItemDrawer — read the picked item from the active review**

In `ItemDrawer.svelte`, replace any `sections`/`updateItem`/`markReviewed` usage so it resolves the picked item from `$activeVersion` + `$activeReview`:

```ts
	import { activeReview, activeVersion, picked, drawerOpen, updateItemResult, markReviewed } from '../lib/store';

	let sec = $derived(
		$picked ? $activeVersion?.sections.find((s) => s.id === $picked!.sectionId) ?? null : null
	);
	let def = $derived(sec && $picked ? sec.items.find((i) => i.n === $picked!.n) ?? null : null);
	let itemId = $derived(def ? def.id : null);
	let result = $derived(itemId ? $activeReview?.results[itemId] ?? { result: 'pending' } : null);
```

Wire any verdict/override/comment buttons to `updateItemResult($activeReview!.id, itemId!, { ... })` and the deep-review button to `markReviewed($activeReview!.id, itemId!)`. Read display fields (`text`, `codes`) from `def`, and (`result`, `comment`, `ref`, `confidence`) from `result`.

- [ ] **Step 2: SubmitApprovalModal — submit the active review**

In `SubmitApprovalModal.svelte`, change the submit handler to call `submitForApproval($activeReview!.id, note)`:

```ts
	import { submitModalOpen, activeReview, submitForApproval } from '../lib/store';
	// on confirm:
	function confirm() {
		if ($activeReview) submitForApproval($activeReview.id, note);
		submitModalOpen.set(false);
	}
```

- [ ] **Step 3: ApprovalBanner — read/act on the active review**

In `ApprovalBanner.svelte`, read `$activeReview.approval` and gate the approver buttons behind `$canApprove`, calling `approveAndPublish($activeReview!.id, note)` / `rejectPolicy($activeReview!.id, note)`. Remove the ungated "Reset"; if a reset affordance remains, show it only when `$activeReview.status === 'rejected'`.

```ts
	import { activeReview, canApprove, approveAndPublish, rejectPolicy } from '../lib/store';
	let approval = $derived($activeReview?.approval ?? null);
```

- [ ] **Step 4: PolicyReviewApp — flatten items from the active version for keyboard nav**

In `PolicyReviewApp.svelte`, the arrow-key handler builds a flat list. Replace the `$sections` import with `activeVersion`, and build the flat list from `$activeVersion.sections`:

```ts
	import { view, stage, activeVersion, drawerOpen, picked, canUseChecker } from './lib/store';
	// inside handleKey, replace untrack(() => $sections) with:
	untrack(() => $activeVersion)?.sections.forEach((sec) =>
		sec.items.forEach((it) => flat.push({ sectionId: sec.id, n: it.n }))
	);
```

Leave the `view`/`stage` switch markup as-is (still `all-policies` / `new-review`).

- [ ] **Step 5: ScanningView — animate over the active version, not `SECTIONS`**

`ScanningView.svelte` imports the removed `SECTIONS`. Replace its data source:

```ts
	import { stage, activeVersion, activeReview } from '../lib/store';
	let sections = $derived($activeVersion?.sections ?? []);
	let themes = $derived($activeVersion?.themes ?? []);
	let meta = $derived($activeReview?.policyMeta);
```

Replace every `SECTIONS` reference with `sections`, `THEMES` with `themes`, and `POLICY_META.<x>` with `meta?.<x>`. Keep the "advance to review when done" behavior (`stage.set('review')`) unchanged.

- [ ] **Step 5b: Repoint remaining `./mocks` imports to `./seed`**

These files only need the import path updated (the symbols they use — `POLICIES`, `FN_META`, `TODAY`, `POLICY_META` — are still exported from `seed.ts`):
- `views/AllPoliciesView.svelte`: `import { POLICIES, FN_META, TODAY } from '../lib/seed';`
- `views/PolicyPopup.svelte`: `import { POLICIES, FN_META } from '../lib/seed';`
- `chrome/Topbar.svelte`: `import { POLICY_META } from '../lib/seed';`

In `SubmitApprovalModal.svelte` (edited in Step 2), remove the now-unused `import { POLICY_META } from '../lib/mocks';` line entirely.

- [ ] **Step 5c: ToolSidebar — keep New Review wired to resetReview**

`resetReview()` still exists (Task 8) and the existing `go('new-review')` call works unchanged. No edit needed unless `npm run check` reports a type error here — if it imports removed symbols, drop them.

- [ ] **Step 6: Type-check the whole frontend**

Run: `npm run check`
Expected: no errors across the policy-review tree.

- [ ] **Step 7: Commit**

```bash
git add src/lib/components/policy-review/views/ src/lib/components/policy-review/chrome/ src/lib/components/policy-review/PolicyReviewApp.svelte
git commit -m "refactor(policy-review): overlays, shell, scanning + library read the per-review model"
```

---

### Task 11: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full frontend test suite**

Run: `npx vitest run`
Expected: PASS — including `seed.test.ts`, `checklist.test.ts`, `scoring.test.ts`, `store.test.ts`, and the existing `roles.test.ts` / `library.test.ts`. If `library.test.ts` imported from `mocks.ts`, update its import to `./seed`.

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: no errors.

- [ ] **Step 3: Manual smoke test**

Run: `npm run dev`, open `/policy-review`. Confirm:
- The Library (All Policies) renders.
- "New Review" → upload → (click) → scanning → review renders the workspace with the real T1–T6 themes, scores, and the side rail.
- Opening an item drawer shows the item; overriding a verdict updates the score.
- "Submit for Approval" is disabled while human items remain.

- [ ] **Step 4: Commit any import fixups**

```bash
git add -A
git commit -m "test(policy-review): point remaining imports at seed; green suite + check"
```

---

## Self-review notes

- **Spec coverage (Plan 1 slice):** `policy_admin` permission (Tasks 1–3, gate in Task 8 `canAdmin`); definition/review split (Task 4); versioned checklist + snapshot (Tasks 5, 8); checklist validate/publish (Task 6); scoring from `(version, results)` (Task 7); reviews collection + lifecycle mutators + derived queues + library-from-approved (Task 8); existing UI kept working (Tasks 9–10). Deferred to Plan 2/3 by design: new IA/views (Overview, My reviews, Approval queue, lean nav) and the admin page UI.
- **Type consistency:** `itemId = "${sectionId}-${n}"` used in seed, scoring, store, ItemDrawer; `updateItemResult(reviewId, itemId, patch)`, `submitForApproval(reviewId, note)`, `approveAndPublish(reviewId, note?)`, `rejectPolicy(reviewId, note?)` signatures match across store + overlays.
- **No placeholders:** every code step shows full code or an exact mechanical edit list.
- **Dangling imports check:** every file that imported `./mocks` is reassigned — `ReviewView` (Task 9), `ItemDrawer`/`SubmitApprovalModal`/`PolicyReviewApp` (Task 10), `ScanningView`/`Topbar`/`PolicyPopup`/`AllPoliciesView` (Task 10 Step 5b), `store`/`scoring.test` (rewritten in Tasks 7–8), `library.test` (Task 11 Step 1). `SECTIONS` is no longer exported, so `ScanningView` is rewired to `$activeVersion.sections`.
