# Policy Review Visibility Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hide the in-development Policy Review tool from regular users behind an admin-toggleable `ENABLE_POLICY_REVIEW` flag (default off); admins and `policy_checker` users always see it.

**Architecture:** Clone the existing `ENABLE_NOTES` PersistentConfig pattern end-to-end: backend flag stored in webui.db → exposed in `/api/config` `features` → admin switch in Admin Settings → General. A single shared frontend predicate `canSeePolicyReview()` gates both the rail item and the route.

**Tech Stack:** FastAPI backend (OWUI fork), SvelteKit frontend (Svelte 5, mixed legacy/runes components), pytest (`backend/venv/Scripts/pytest.exe`), vitest.

**Spec:** `docs/superpowers/specs/2026-08-24-policy-review-visibility-toggle-design.md`

## Global Constraints

- Repo: `C:/Projects/open-webui`, branch `osool`. All paths below relative to repo root.
- Flag default is **False** (hidden) — both the env-var fallback and any test expectations.
- Config key path: `policy_review.enable`; env var: `ENABLE_POLICY_REVIEW`.
- Visibility rule (exactly): `config.features.enable_policy_review === true` OR `user.role === 'admin'` OR `user.permissions.features.policy_checker` truthy.
- WorkOS rail item must NOT be touched.
- Backend tests: `cd backend` then `venv/Scripts/pytest.exe open_webui/test/policy_review/... -v` (the `policy_review` conftest sets up the SQLite test DB before `open_webui.config` import).
- Frontend tests: `npx vitest run <path>` from repo root.

---

### Task 1: Backend `ENABLE_POLICY_REVIEW` flag

**Files:**
- Modify: `backend/open_webui/config.py` (after `ENABLE_NOTES`, line ~1739)
- Modify: `backend/open_webui/main.py` (import ~line 419, app.state ~line 966, features dict ~line 2443)
- Modify: `backend/open_webui/routers/auths.py` (GET dict ~line 1023, `AdminConfig` model ~line 1053, POST setter ~line 1086, POST response ~line 1131)
- Test: `backend/open_webui/test/policy_review/test_config_flag.py` (create)

**Interfaces:**
- Consumes: existing `PersistentConfig` class in `config.py`.
- Produces: `app.state.config.ENABLE_POLICY_REVIEW` (bool); `/api/config` response gains `features.enable_policy_review`; `GET/POST /api/v1/auths/admin/config` gains `ENABLE_POLICY_REVIEW`. Task 2's predicate reads `config.features.enable_policy_review`; Task 4's switch binds `adminConfig.ENABLE_POLICY_REVIEW`.

- [ ] **Step 1: Write the failing test**

Create `backend/open_webui/test/policy_review/test_config_flag.py`:

```python
def test_policy_review_flag_defaults_off():
    from open_webui.config import ENABLE_POLICY_REVIEW

    assert ENABLE_POLICY_REVIEW.value is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && venv/Scripts/pytest.exe open_webui/test/policy_review/test_config_flag.py -v
```

Expected: FAIL — `ImportError: cannot import name 'ENABLE_POLICY_REVIEW'`

- [ ] **Step 3: Add the PersistentConfig**

In `backend/open_webui/config.py`, directly after the `ENABLE_NOTES` block (ends line 1739):

```python
ENABLE_POLICY_REVIEW = PersistentConfig(
    'ENABLE_POLICY_REVIEW',
    'policy_review.enable',
    os.environ.get('ENABLE_POLICY_REVIEW', 'False').lower() == 'true',
)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && venv/Scripts/pytest.exe open_webui/test/policy_review/test_config_flag.py -v
```

Expected: PASS

- [ ] **Step 5: Wire into main.py (three places)**

In `backend/open_webui/main.py`:

a. In the `from open_webui.config import (...)` block, after `ENABLE_NOTES,` (line ~419):

```python
    ENABLE_POLICY_REVIEW,
```

b. After `app.state.config.ENABLE_NOTES = ENABLE_NOTES` (line ~966):

```python
app.state.config.ENABLE_POLICY_REVIEW = ENABLE_POLICY_REVIEW
```

c. In the `/api/config` features dict, after `'enable_notes': app.state.config.ENABLE_NOTES,` (line ~2443):

```python
                    'enable_policy_review': app.state.config.ENABLE_POLICY_REVIEW,
```

- [ ] **Step 6: Wire into auths.py (four places)**

In `backend/open_webui/routers/auths.py`:

a. GET admin config dict, after `'ENABLE_NOTES': ...` (line ~1023):

```python
        'ENABLE_POLICY_REVIEW': request.app.state.config.ENABLE_POLICY_REVIEW,
```

b. `AdminConfig` model, after `ENABLE_NOTES: bool` (line ~1053):

```python
    ENABLE_POLICY_REVIEW: bool
```

c. POST setter, after `request.app.state.config.ENABLE_NOTES = form_data.ENABLE_NOTES` (line ~1086):

```python
    request.app.state.config.ENABLE_POLICY_REVIEW = form_data.ENABLE_POLICY_REVIEW
```

d. POST response dict, after `'ENABLE_NOTES': ...` (line ~1131):

```python
        'ENABLE_POLICY_REVIEW': request.app.state.config.ENABLE_POLICY_REVIEW,
```

- [ ] **Step 7: Run the policy_review backend suite (regression)**

```bash
cd backend && venv/Scripts/pytest.exe open_webui/test/policy_review -v
```

Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add backend/open_webui/config.py backend/open_webui/main.py backend/open_webui/routers/auths.py backend/open_webui/test/policy_review/test_config_flag.py
git commit -m "feat(policy-review): ENABLE_POLICY_REVIEW persistent config flag, default off"
```

---

### Task 2: Shared visibility predicate + rail item gating

**Files:**
- Create: `src/lib/components/policy-review/lib/visibility.ts`
- Modify: `src/lib/components/app/railItems.ts:84-95` (the `policy-review` entry only)
- Test: `src/lib/components/policy-review/lib/visibility.test.ts` (create)

**Interfaces:**
- Consumes: `config.features.enable_policy_review` from Task 1 (via the `/api/config` payload stored in the `config` store).
- Produces: `canSeePolicyReview(ctx: { user: any; config: any }): boolean` — used by `railItems.ts` here and by the route guard in Task 3. Context shape is structurally identical to `RailVisibilityContext` in `railItems.ts`.

- [ ] **Step 1: Write the failing tests**

Create `src/lib/components/policy-review/lib/visibility.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { canSeePolicyReview } from './visibility';

const cfg = (enabled: boolean) => ({ features: { enable_policy_review: enabled } });

describe('canSeePolicyReview', () => {
	it('shows the tool to everyone when the flag is on', () => {
		expect(canSeePolicyReview({ user: { role: 'user' }, config: cfg(true) })).toBe(true);
	});

	it('hides the tool from plain users when the flag is off', () => {
		expect(canSeePolicyReview({ user: { role: 'user' }, config: cfg(false) })).toBe(false);
	});

	it('always shows the tool to admins', () => {
		expect(canSeePolicyReview({ user: { role: 'admin' }, config: cfg(false) })).toBe(true);
	});

	it('always shows the tool to policy_checker users', () => {
		const user = { role: 'user', permissions: { features: { policy_checker: true } } };
		expect(canSeePolicyReview({ user, config: cfg(false) })).toBe(true);
	});

	it('treats a missing flag as off (config not loaded yet)', () => {
		expect(canSeePolicyReview({ user: { role: 'user' }, config: undefined })).toBe(false);
		expect(canSeePolicyReview({ user: { role: 'user' }, config: {} })).toBe(false);
	});

	it('treats a missing or false policy_checker permission as no access', () => {
		expect(canSeePolicyReview({ user: { role: 'user', permissions: {} }, config: cfg(false) })).toBe(false);
		const user = { role: 'user', permissions: { features: { policy_checker: false } } };
		expect(canSeePolicyReview({ user, config: cfg(false) })).toBe(false);
	});

	it('handles a null user (logged-out edge) without crashing', () => {
		expect(canSeePolicyReview({ user: null, config: cfg(false) })).toBe(false);
		expect(canSeePolicyReview({ user: null, config: cfg(true) })).toBe(true);
	});
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
npx vitest run src/lib/components/policy-review/lib/visibility.test.ts
```

Expected: FAIL — cannot resolve `./visibility`

- [ ] **Step 3: Implement the predicate**

Create `src/lib/components/policy-review/lib/visibility.ts`:

```ts
/**
 * Single source of truth for who can see the Policy Review tool.
 *
 * Visible when the admin has switched the tool on globally
 * (config.features.enable_policy_review), and always for admins and
 * users with the policy_checker permission — the people building and
 * piloting the tool while it is hidden from everyone else.
 *
 * Used by the rail (railItems.ts) and the route guard
 * (routes/(app)/policy-review/+layout.svelte) so they cannot disagree.
 */
export function canSeePolicyReview({ user, config }: { user: any; config: any }): boolean {
	return (
		(config?.features?.enable_policy_review ?? false) ||
		user?.role === 'admin' ||
		!!user?.permissions?.features?.policy_checker
	);
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx vitest run src/lib/components/policy-review/lib/visibility.test.ts
```

Expected: 7 PASS

- [ ] **Step 5: Gate the rail item**

In `src/lib/components/app/railItems.ts`:

a. Add the import below the icon imports (after line 8):

```ts
import { canSeePolicyReview } from '$lib/components/policy-review/lib/visibility';
```

b. Replace the whole `policy-review` entry (lines 84-95, including its comment) with:

```ts
	{
		// Policy Review tool. Hidden while in development: the
		// ENABLE_POLICY_REVIEW admin toggle (Admin Settings > General) reveals
		// it to everyone; admins and policy_checker users always see it. The
		// checker workflow inside the tool stays gated by canUseChecker
		// (see policy-review/lib/store.ts).
		id: 'policy-review',
		label: 'Policy Review',
		href: '/policy-review',
		icon: DocumentCheck,
		segments: ['policy-review'],
		visible: canSeePolicyReview
	},
```

Do NOT touch the `workos` entry.

- [ ] **Step 6: Full frontend test run + svelte-check (regression)**

```bash
npx vitest run
npm run check 2>&1 | tail -5
```

Expected: vitest all PASS; `npm run check` reports no NEW errors in the touched files. Pre-existing errors elsewhere in the fork are out of scope.

- [ ] **Step 7: Commit**

```bash
git add src/lib/components/policy-review/lib/visibility.ts src/lib/components/policy-review/lib/visibility.test.ts src/lib/components/app/railItems.ts
git commit -m "feat(policy-review): gate rail item behind canSeePolicyReview predicate"
```

---

### Task 3: Route guard on /policy-review

**Files:**
- Modify: `src/routes/(app)/policy-review/+layout.svelte`

**Interfaces:**
- Consumes: `canSeePolicyReview` from Task 2; `user`, `config` stores from `$lib/stores`; `goto` from `$app/navigation`.
- Produces: ineligible users navigating to `/policy-review` (deep link or stale bookmark) are redirected to `/home` before the tool renders.

- [ ] **Step 1: Add the guard**

Replace the full contents of `src/routes/(app)/policy-review/+layout.svelte` with:

```svelte
<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { showSidebar, user, config } from '$lib/stores';
	import { canSeePolicyReview } from '$lib/components/policy-review/lib/visibility';
	import '$lib/components/policy-review/styles.css';

	let { children } = $props();

	// Route guard: same predicate as the rail item, so a deep link can't
	// reach a tool the rail wouldn't show. Reactive so a config refresh
	// that turns the flag off also ejects the user.
	let allowed = $derived(canSeePolicyReview({ user: $user, config: $config }));
	$effect(() => {
		if (!allowed) goto('/home');
	});

	// OWUI's chat sidebar is global; suppress it while the user is inside the
	// Policy Review tool so the design's own internal sidebar isn't covered.
	// Restore the prior visibility when navigating away.
	let prev: boolean | undefined;
	onMount(() => {
		showSidebar.update((v) => {
			prev = v;
			return false;
		});
	});
	onDestroy(() => {
		if (prev !== undefined) showSidebar.set(prev);
	});
</script>

{#if allowed}
	<div class="pr-root w-full h-full">
		{@render children()}
	</div>
{/if}
```

- [ ] **Step 2: Verify with svelte-check scoped to the file**

```bash
npm run check 2>&1 | tail -5
```

Expected: no NEW errors mentioning `policy-review/+layout.svelte`. Pre-existing errors elsewhere are out of scope.

- [ ] **Step 3: Commit**

```bash
git add "src/routes/(app)/policy-review/+layout.svelte"
git commit -m "feat(policy-review): route guard redirects ineligible users to /home"
```

---

### Task 4: Admin Settings switch

**Files:**
- Modify: `src/lib/components/admin/Settings/General.svelte` (features block, after the Notes switch at lines 632-638)

**Interfaces:**
- Consumes: `adminConfig.ENABLE_POLICY_REVIEW` — present in the GET/POST admin config payloads from Task 1. `Switch` component and `adminConfig` object already exist in this file.
- Produces: admin-facing toggle "Policy Review (Beta)".

- [ ] **Step 1: Add the switch**

In `src/lib/components/admin/Settings/General.svelte`, directly after the Notes switch block (lines 632-638):

```svelte
					<div class="mb-2.5 flex w-full items-center justify-between pr-2">
						<div class=" self-center text-xs font-medium">
							{$i18n.t('Policy Review')} ({$i18n.t('Beta')})
						</div>

						<Switch bind:state={adminConfig.ENABLE_POLICY_REVIEW} />
					</div>
```

(Indentation: match the sibling blocks — tabs, same depth as the Notes block.)

- [ ] **Step 2: Commit**

```bash
git add src/lib/components/admin/Settings/General.svelte
git commit -m "feat(admin): Policy Review visibility switch in General settings"
```

---

### Task 5: Manual smoke test (dev loop)

**Files:** none (verification only)

**Interfaces:**
- Consumes: everything above, running under the dev loop (backend `dev.sh`/uvicorn + `npm run dev` on localhost:5173).

- [ ] **Step 1: Restart backend + frontend dev servers** (backend restart required — config.py/main.py changed)

- [ ] **Step 2: As a regular user (ahmad@ahmad.com), verify hidden**

Expected: no "Policy Review" in the rail; navigating to `localhost:5173/policy-review` redirects to `/home`.

- [ ] **Step 3: As admin, verify always visible + toggle works**

Expected: rail shows Policy Review. Admin Settings → General shows "Policy Review (Beta)" switch, default OFF. Turn ON, save; regular user (after reload) now sees the rail item and can open the tool. Turn OFF, save; regular user loses it again — no rebuild, no restart.

- [ ] **Step 4: Verify persistence**

Restart the backend; switch stays in its last saved state (webui.db `policy_review.enable`).

- [ ] **Step 5: Done — hand back for merge decision** (superpowers:finishing-a-development-branch)
