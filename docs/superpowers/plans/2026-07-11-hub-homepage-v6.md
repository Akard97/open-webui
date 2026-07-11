# Hub Homepage v6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `docs/mockups/hub-homepage-v6.html` as the real `/home` page and make `/home` the post-login landing page.

**Architecture:** Single Svelte page component (`src/routes/(app)/home/+page.svelte`) with the mockup's CSS ported verbatim into the scoped `<style>` block. A tiny pure helper module (`greeting.ts`) carries the only logic worth unit-testing. The app's root layout already renders the rail (`AppSidebar`), so the mockup's `.rail` and `.mockbar` are NOT ported.

**Tech Stack:** SvelteKit (Svelte 4 syntax), Tailwind 4 global vars (`--color-brand-*`, `--color-gray-*` in `src/tailwind.css`), vitest, svelte-sonner toasts, i18next via `getContext('i18n')`.

**Spec:** `docs/superpowers/specs/2026-07-11-hub-homepage-design.md`

## Global Constraints

- All user-visible strings go through `$i18n.t('…')`. Do NOT edit locale JSON files — i18next falls back to the key text (English) for missing keys.
- Images must be Vite-bundled imports. Never `/static/...` URLs (standing project rule: the backend static copy is wiped on image rebuild).
- Dark mode follows the `.dark` class on `<html>`; in scoped Svelte CSS every mockup `.dark X` selector becomes `:global(.dark) X`.
- Logical properties from the mockup (`inset-inline-end`, `margin-inline-start`) must be kept as-is (RTL safety).
- Keep the mockup's `@media (prefers-reduced-motion: reduce)` block.
- NEVER use a haiku-model subagent for Svelte edits (cp1252 corruption risk, standing rule). Write files as UTF-8.
- Do not start a Vite dev server without asking the user first (standing rule).
- Commit after every task. Commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Greeting helper (TDD)

**Files:**
- Create: `src/routes/(app)/home/greeting.ts`
- Test: `src/routes/(app)/home/greeting.test.ts`

**Interfaces:**
- Produces (Task 4 consumes):
  - `greetingForHour(h: number): 'morning' | 'afternoon' | 'evening'`
  - `daymarkForHour(h: number): 'sun' | 'moon'`
  - `wishForHour(h: number): 'bright' | 'rest' | 'calm'`

- [ ] **Step 1: Write the failing test**

Create `src/routes/(app)/home/greeting.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { greetingForHour, daymarkForHour, wishForHour } from './greeting';

describe('greetingForHour', () => {
	it('morning strictly before 12', () => {
		expect(greetingForHour(0)).toBe('morning');
		expect(greetingForHour(6)).toBe('morning');
		expect(greetingForHour(11)).toBe('morning');
	});
	it('afternoon from 12 strictly before 17', () => {
		expect(greetingForHour(12)).toBe('afternoon');
		expect(greetingForHour(16)).toBe('afternoon');
	});
	it('evening from 17', () => {
		expect(greetingForHour(17)).toBe('evening');
		expect(greetingForHour(23)).toBe('evening');
	});
});

describe('daymarkForHour', () => {
	it('moon from 19:00 and before 06:00', () => {
		expect(daymarkForHour(19)).toBe('moon');
		expect(daymarkForHour(23)).toBe('moon');
		expect(daymarkForHour(0)).toBe('moon');
		expect(daymarkForHour(5)).toBe('moon');
	});
	it('sun from 06:00 strictly before 19:00', () => {
		expect(daymarkForHour(6)).toBe('sun');
		expect(daymarkForHour(12)).toBe('sun');
		expect(daymarkForHour(18)).toBe('sun');
	});
});

describe('wishForHour', () => {
	it('bright strictly before 12', () => {
		expect(wishForHour(0)).toBe('bright');
		expect(wishForHour(11)).toBe('bright');
	});
	it('rest from 12 strictly before 17', () => {
		expect(wishForHour(12)).toBe('rest');
		expect(wishForHour(16)).toBe('rest');
	});
	it('calm from 17', () => {
		expect(wishForHour(17)).toBe('calm');
		expect(wishForHour(23)).toBe('calm');
	});
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run "src/routes/(app)/home/greeting.test.ts"`
Expected: FAIL — cannot resolve `./greeting`.

- [ ] **Step 3: Write minimal implementation**

Create `src/routes/(app)/home/greeting.ts`:

```ts
/**
 * Pure time-of-day buckets for the /home hero. Thresholds mirror
 * docs/mockups/hub-homepage-v6.html. The component maps these
 * discriminants to i18n strings.
 */
export type Greeting = 'morning' | 'afternoon' | 'evening';
export type Daymark = 'sun' | 'moon';
export type Wish = 'bright' | 'rest' | 'calm';

export function greetingForHour(h: number): Greeting {
	if (h < 12) return 'morning';
	if (h < 17) return 'afternoon';
	return 'evening';
}

export function daymarkForHour(h: number): Daymark {
	return h >= 19 || h < 6 ? 'moon' : 'sun';
}

export function wishForHour(h: number): Wish {
	if (h < 12) return 'bright';
	if (h < 17) return 'rest';
	return 'calm';
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run "src/routes/(app)/home/greeting.test.ts"`
Expected: PASS (3 suites, 8 tests).

- [ ] **Step 5: Commit**

```bash
git add "src/routes/(app)/home/greeting.ts" "src/routes/(app)/home/greeting.test.ts"
git commit -m "feat(home): time-of-day greeting helper"
```

---

### Task 2: Bundle hub assets

**Files:**
- Create: `src/lib/assets/favicon.png`, `src/lib/assets/favicon-dark.png`, `src/lib/assets/osool-ai-logo-black-transparent.png`, `src/lib/assets/osool-ai-logo-whitish-transparent.png` (copies of the same-named files in `static/static/`)

**Interfaces:**
- Produces (Task 4 consumes): the four import paths
  `$lib/assets/favicon.png`, `$lib/assets/favicon-dark.png`,
  `$lib/assets/osool-ai-logo-black-transparent.png`,
  `$lib/assets/osool-ai-logo-whitish-transparent.png`.
- WorkOS logos are NOT copied — Task 4 imports the existing
  `$lib/components/workos/assets/workos-logo-dark.png` and
  `$lib/components/workos/assets/workos-logo-light.png`.

- [ ] **Step 1: Copy files** (PowerShell)

```powershell
Copy-Item static/static/favicon.png src/lib/assets/
Copy-Item static/static/favicon-dark.png src/lib/assets/
Copy-Item static/static/osool-ai-logo-black-transparent.png src/lib/assets/
Copy-Item static/static/osool-ai-logo-whitish-transparent.png src/lib/assets/
```

- [ ] **Step 2: Verify**

Run: `git status --short src/lib/assets`
Expected: four `??` (untracked) entries.

- [ ] **Step 3: Commit**

```bash
git add src/lib/assets
git commit -m "chore(home): bundle hub logo assets as Vite imports"
```

---

### Task 3: Gut the stale /home layout

**Files:**
- Modify: `src/routes/(app)/home/+layout.svelte` (replace entire file — current content is a stale upstream leftover with a Notes/Calendar nav pointing at `/playground`)

**Interfaces:**
- Produces: a plain full-height scroll container; Task 4's page fills it.

- [ ] **Step 1: Replace the file**

Full new content of `src/routes/(app)/home/+layout.svelte`:

```svelte
<script lang="ts">
	import { getContext } from 'svelte';
	import { WEBUI_NAME } from '$lib/stores';

	const i18n = getContext<any>('i18n');
</script>

<svelte:head>
	<title>
		{$i18n.t('Home')} • {$WEBUI_NAME}
	</title>
</svelte:head>

<div class="w-full h-full max-h-[100dvh] overflow-y-auto">
	<slot />
</div>
```

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: no errors reported for `src/routes/(app)/home/+layout.svelte`. (Pre-existing errors elsewhere in the repo, if any, are out of scope.)

- [ ] **Step 3: Commit**

```bash
git add "src/routes/(app)/home/+layout.svelte"
git commit -m "refactor(home): strip stale upstream home layout to a scroll container"
```

---

### Task 4: The /home page (v6 port)

**Files:**
- Modify: `src/routes/(app)/home/+page.svelte` (replace entire file — currently a one-line placeholder)
- Read (source of truth): `docs/mockups/hub-homepage-v6.html`

**Interfaces:**
- Consumes: Task 1's `greetingForHour/daymarkForHour/wishForHour` from `./greeting`; Task 2's asset imports; `$user` from `$lib/stores`; `toast` from `svelte-sonner`.

This task ports the mockup. The mockup file is in-repo and authoritative; the steps below give the complete script block, the complete transformed markup skeleton, and a deterministic CSS recipe.

- [ ] **Step 1: Write the `<script>` block**

```svelte
<script lang="ts">
	import { onMount, onDestroy, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	import { user } from '$lib/stores';

	import osoolMark from '$lib/assets/favicon.png';
	import osoolMarkDark from '$lib/assets/favicon-dark.png';
	import osoolAiLogoBlack from '$lib/assets/osool-ai-logo-black-transparent.png';
	import osoolAiLogoWhite from '$lib/assets/osool-ai-logo-whitish-transparent.png';
	import workosLogoDark from '$lib/components/workos/assets/workos-logo-dark.png';
	import workosLogoLight from '$lib/components/workos/assets/workos-logo-light.png';

	import { greetingForHour, daymarkForHour, wishForHour } from './greeting';

	const i18n = getContext<any>('i18n');

	// Computed once on load, like the mockup.
	const now = new Date();
	const h = now.getHours();
	const daymark = daymarkForHour(h);

	$: weekday = now.toLocaleDateString($i18n.language, { weekday: 'long' });
	$: dateText = now.toLocaleDateString($i18n.language, {
		weekday: 'long',
		month: 'long',
		day: 'numeric'
	});

	$: greetingText = {
		morning: $i18n.t('Good morning'),
		afternoon: $i18n.t('Good afternoon'),
		evening: $i18n.t('Good evening')
	}[greetingForHour(h)];

	$: wishText = {
		bright: $i18n.t('have a bright {{weekday}}', { weekday }),
		rest: $i18n.t('enjoy the rest of your {{weekday}}', { weekday }),
		calm: $i18n.t('have a calm evening')
	}[wishForHour(h)];

	$: firstName = ($user?.name ?? '').trim().split(/\s+/)[0] ?? '';

	const notifyMe = () => {
		toast.success($i18n.t("We'll let you know when it's ready."));
	};

	let pageEl: HTMLElement;
	let io: IntersectionObserver | undefined;

	onMount(() => {
		io = new IntersectionObserver(
			(entries) => {
				for (const e of entries) {
					if (e.isIntersecting) {
						e.target.classList.add('in');
						io?.unobserve(e.target);
					}
				}
			},
			{ threshold: 0.12 }
		);
		pageEl.querySelectorAll('.reveal').forEach((el) => io?.observe(el));
	});

	onDestroy(() => {
		io?.disconnect();
	});
</script>
```

- [ ] **Step 2: Write the markup**

Structure (mockup lines 559–839, transformed). Root element replaces the mockup's `body` flex pairing:

```svelte
<div class="home-root" bind:this={pageEl}>
	<!-- SVG symbol defs: copy mockup lines 559–584 VERBATIM
	     (the warmline gradient + all <symbol id="i-*"> icons). -->

	<div class="wrap">
		<div class="frame">
			<!-- HERO: mockup lines 604–681 with these substitutions -->
			<!-- FEATURE/TOOLS: mockup lines 684–835 with these substitutions -->
			<!-- FOOTER: see below -->
		</div>
	</div>
</div>
```

Do NOT port: the mockup's `<nav class="rail">` (app rail already exists), the `.mockbar` div, and the mockup's entire `<script>` tag (replaced by Step 1).

Substitutions inside the copied markup — every one listed, apply exactly:

**Hero copy block** (mockup lines 618–622) becomes:

```svelte
<div class="hero-copy">
	<span class="eyebrow"
		><svg class="icon"><use href={daymark === 'moon' ? '#i-moon' : '#i-sun'} /></svg><span
			>{dateText}</span
		></span
	>
	<h1>
		{greetingText}{#if firstName},
			<span class="name"
				>{firstName}<svg class="uline" viewBox="0 0 120 12" preserveAspectRatio="none" aria-hidden="true"
					><path d="M3 9 C 28 3.5, 62 3, 117 6.5" pathLength="100" /></svg
				></span
			>{/if}
	</h1>
	<p class="sub">{$i18n.t("Everything you need is right here — let's make today count.")}</p>
</div>
```

**Hero viz** (mockup lines 624–679): copy verbatim, then replace image srcs:
- `src="../../static/static/favicon.png"` → `src={osoolMark}`
- `src="../../static/static/favicon-dark.png"` → `src={osoolMarkDark}`
- `src="../../static/static/osool-ai-logo-black-transparent.png"` → `src={osoolAiLogoBlack}`
- `src="../../static/static/osool-ai-logo-whitish-transparent.png"` → `src={osoolAiLogoWhite}`
- `src="../../static/static/workos-logo-dark.png"` → `src={workosLogoDark}`
- `src="../../static/static/workos-logo-light.png"` → `src={workosLogoLight}`
- Satellite labels: `<span class="lbl">Osool AI</span>` → `<span class="lbl">{$i18n.t('Osool AI')}</span>`; same for `WorkOS`, `Knowledge`, `Notifications`, `Policies`.
- Tiny chips: `Due Sun` → `{$i18n.t('Due Sun')}`, `@ahmed` → `{$i18n.t('@ahmed')}`, `HR-POL-014` stays literal (document code).
- `alt="Osool Intelligence Hub"` → `alt={$i18n.t('Osool Intelligence Hub')}`.

(The same six src replacements apply everywhere else in the page: tool heads and appcard heads.)

**Osool AI tool column** (mockup lines 689–728), text/link substitutions:
- `<span class="t"><b>Osool AI</b></span>` → `<b>{$i18n.t('Osool AI')}</b>`
- `<a class="go" href="#">Open …</a>` → `<a class="go" href="/">{$i18n.t('Open')} <svg class="icon"><use href="#i-arrow" /></svg></a>`
- apphead: `<b>Osool AI</b>` → `{$i18n.t('Osool AI')}`; `<small>Connected to company knowledge</small>` → `{$i18n.t('Connected to company knowledge')}`; `Online` → `{$i18n.t('Online')}`
- chat vignette:
  - `<div class="msg q">What's our remote work policy?</div>` → `{$i18n.t("What's our remote work policy?")}`
  - answer line → `{$i18n.t('Remote work is allowed up to')} <b>{$i18n.t('3 days per week')}</b> {$i18n.t('with manager approval…')}`
  - source pills: `HR-POL-014` literal; `Handbook §4` → `{$i18n.t('Handbook §4')}`
  - `<span>Ask anything…</span>` → `{$i18n.t('Ask anything…')}`
  - send button `aria-label="Send"` → `aria-label={$i18n.t('Send')}`; it is decorative — add `tabindex="-1"` and leave it a `<button type="button">` with no handler.
- float chip: `2 sources cited` → `{$i18n.t('2 sources cited')}`; `From your knowledge base` → `{$i18n.t('From your knowledge base')}`

**WorkOS tool column** (mockup lines 731–775), substitutions:
- head `<b>WorkOS</b>` → `{$i18n.t('WorkOS')}`; `<a class="go" href="#">` → `href="/workos"`; `Open` → `{$i18n.t('Open')}`
- apphead: `Marketing Q3` → `{$i18n.t('Marketing Q3')}`; `Board • 3 workstreams` → `{$i18n.t('Board • 3 workstreams')}`; `4 online` → `{$i18n.t('4 online')}`
- kanban: `To do` → `{$i18n.t('To do')}`, `Doing` → `{$i18n.t('Doing')}`; card titles `Vendor contract renewal`, `Onboarding checklist v2`, `Q3 policy audit` → each `{$i18n.t('…')}`; priority pills `Medium`/`Low`/`High` → each `{$i18n.t('…')}`
- float chip: `Sarah mentioned you` → `{$i18n.t('Sarah mentioned you')}`; `"@ahmed can you review this?"` → `{$i18n.t('"@ahmed can you review this?"')}`

**Coming-soon column** (mockup lines 778–831), substitutions:
- `Coming soon` → `{$i18n.t('Coming soon')}`; head-note `+ Intelligence Survey` → `{$i18n.t('+ Intelligence Survey')}`
- Card 1: `Presentation Maker` → `{$i18n.t('Presentation Maker')}`; `On-brand decks by AI` → `{$i18n.t('On-brand decks by AI')}`; `Soon` → `{$i18n.t('Soon')}`; `In design` → `{$i18n.t('In design')}`
- Card 2: `Policies Library` → `{$i18n.t('Policies Library')}`; `Search &amp; acknowledge` → `{$i18n.t('Search & acknowledge')}`; `In development` → `{$i18n.t('In development')}`
- Both `<a class="notify" href="#">…Notify me</a>` become buttons:

```svelte
<button type="button" class="notify" on:click={notifyMe}
	><svg class="icon"><use href="#i-bell" /></svg> {$i18n.t('Notify me')}</button
>
```

(Add `background: transparent; border: none; cursor: pointer; font: inherit;` to the `.notify` CSS rule since it changes from `<a>` to `<button>`.)

**Footer** (mockup line 837) becomes:

```svelte
<footer>
	{$i18n.t('Osool Intelligence Hub — internal platform')} · <span class="wish">{wishText}</span>
</footer>
```

- [ ] **Step 3: Write the `<style>` block (deterministic recipe)**

Copy mockup CSS (lines 7–554) into the component `<style>` block, then apply:

**Drop these blocks entirely:**
| Mockup block | Reason |
| --- | --- |
| both `@font-face` rules (lines 9–18) | app loads Inter/Archivo in `src/app.css` |
| `* { box-sizing… }` and `body { … }` (lines 104–113) | app-level resets exist; body styling replaced by `.home-root` below |
| `::selection` rule (line 118) | app-global concern |
| `::-webkit-scrollbar*` rules (lines 120–125) | app has its own scrollbar styling |
| `.rail` block, `.rail *` rules (lines 150–177) | app rail exists |
| `.mockbar` block (lines 532–540) | mock-only control |

**Replace the `:root { … }` selector** (line 20) with `.home-root { … }`, and inside it replace the raw ramp definitions (lines 22–44) with references to the global ramps — the semantic layer (lines 46–74) stays byte-identical:

```css
.home-root {
	/* ramps come from src/tailwind.css */
	--gray-50: var(--color-gray-50);
	--gray-100: var(--color-gray-100);
	--gray-200: var(--color-gray-200);
	--gray-300: var(--color-gray-300);
	--gray-400: var(--color-gray-400);
	--gray-500: var(--color-gray-500);
	--gray-600: var(--color-gray-600);
	--gray-700: var(--color-gray-700);
	--gray-800: var(--color-gray-800);
	--gray-850: var(--color-gray-850);
	--gray-900: var(--color-gray-900);
	--gray-950: var(--color-gray-950);

	--brand-100: var(--color-brand-100);
	--brand-200: var(--color-brand-200);
	--brand-300: var(--color-brand-300);
	--brand-400: var(--color-brand-400);
	--brand-500: var(--color-brand-500);
	--brand-600: var(--color-brand-600);
	--brand-700: var(--color-brand-700);
	--brand-900: var(--color-brand-900);
	--success: var(--color-success);

	/* …then lines 46–74 of the mockup verbatim (sun layer + semantic vars + shadows)… */
}
```

**Add** (replaces the mockup's `body` responsibilities):

```css
.home-root {
	min-height: 100%;
	background: var(--backdrop);
	color: var(--ink);
	font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Vazirmatn', ui-sans-serif, system-ui,
		'Segoe UI', Roboto, Ubuntu, Cantarell, 'Noto Sans', sans-serif;
	-webkit-font-smoothing: antialiased;
	text-rendering: optimizeLegibility;
}
```

(Merge with the vars — one `.home-root` rule is fine.)

**Dark-mode variables block** (mockup lines 76–102, `.dark { --sun-tint… --shadow-m }`): becomes `:global(.dark) .home-root { … }` — NOT bare `:global(.dark)`. Critical: names like `--accent`, `--card`, `--border`, `--muted` are also shadcn tokens; defining them on `html.dark` would clobber the WorkOS design system app-wide. Scoping to `.home-root` contains them (the home page contains no shadcn components).

**Selector transforms (find → replace, all remaining selectors):**
| Find | Replace |
| --- | --- |
| `.dark ` (every other selector starting with it, e.g. `.dark .viz svg.wires path`) | `:global(.dark) ` |
| `html:not(.dark) .dark-only` | `:global(html:not(.dark)) .dark-only` |
| `.dark .light-only` | `:global(.dark) .light-only` |

**`.wrap` rule** (line 180): change `flex: 1; min-width: 0; padding: 0.9rem 0.9rem 0.9rem 0;` → `padding: 0.9rem;` (page no longer sits beside an in-flow rail; symmetric padding).

**`.notify` rule** (line 520): append `background: transparent; border: none; cursor: pointer; font: inherit;` (now a `<button>`).

Keep everything else byte-identical, including all `@keyframes`, `@media` blocks, `color-mix()` uses, and the `prefers-reduced-motion` block. Svelte auto-scopes keyframe names — declarations and `animation:` references in the same component keep working.

- [ ] **Step 4: Compile check + unused-selector audit**

Run: `npm run check`
Expected: 0 errors for `src/routes/(app)/home/+page.svelte`. Treat `css-unused-selector` warnings on this file as bugs: each one means a markup chunk was dropped or a selector was mangled — fix, don't suppress. (Exception: none expected; every mockup selector kept has matching markup.)

- [ ] **Step 5: Run the full frontend test suite**

Run: `npx vitest run`
Expected: PASS including Task 1's greeting tests; no regressions.

- [ ] **Step 6: Commit**

```bash
git add "src/routes/(app)/home/+page.svelte"
git commit -m "feat(home): hub homepage from v6 mockup"
```

---

### Task 5: Post-login landing → /home

**Files:**
- Modify: `src/routes/auth/+page.svelte:63` and `src/routes/auth/+page.svelte:171`

**Interfaces:**
- Consumes: nothing from other tasks. Explicit `?redirect=` params must keep working unchanged (only the fallback changes).

- [ ] **Step 1: Change the two fallbacks**

Edit 1 — inside `setSessionUser` (line ~63):

```ts
// before
			if (!redirectPath) {
				redirectPath = $page.url.searchParams.get('redirect') || '/';
			}
// after
			if (!redirectPath) {
				redirectPath = $page.url.searchParams.get('redirect') || '/home';
			}
```

Edit 2 — inside `onMount` (line ~171):

```ts
// before
		if ($user !== undefined) {
			goto(redirectPath || '/');
// after
		if ($user !== undefined) {
			goto(redirectPath || '/home');
```

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: no errors for `src/routes/auth/+page.svelte`.

- [ ] **Step 3: Commit**

```bash
git add src/routes/auth/+page.svelte
git commit -m "feat(auth): land on /home after login"
```

---

### Task 6: Browser smoke (light + dark)

**Files:** none (verification only).

**IMPORTANT:** Do not start a Vite dev server yourself. ASK THE USER first (standing rule) — they usually run their own hot-reload server.

- [ ] **Step 1: Get a running frontend** — ask the user whether their Vite server is up, or for permission to start one.

- [ ] **Step 2: Smoke checklist on `/home`** (both light and dark — toggle via the app's theme switcher):
  - Hero renders: real first name, localized date, correct greeting bucket for current hour, sun/moon mark correct.
  - Name underline draws in; constellation floats; wire dashes move.
  - Tools row: Osool AI "Open" navigates to `/` (chat); WorkOS "Open" navigates to `/workos`; browser Back returns to `/home`.
  - "Notify me" (both cards) shows the success toast.
  - Reveal-on-scroll triggers on the tools row.
  - Footer wish matches the hour bucket.
  - Logos correct per theme (light-only/dark-only swap).
  - No console errors (check DevTools/console tooling).
  - Narrow viewport: at ≤1020px the coming-soon column spans full width (cards side-by-side); at ≤760px single column, viz hidden.
  - Log out, log back in → lands on `/home`; visit `/auth?redirect=/workos` while logged in → lands on `/workos`.

- [ ] **Step 3: Report results** — list each checklist item pass/fail to the user. Fix any failures before calling the task done.
