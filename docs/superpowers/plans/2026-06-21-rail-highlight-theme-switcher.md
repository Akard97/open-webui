# Rail Highlight Fix + Theme Switcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the global rail's active-item highlight track the current route, and add a Light/Dark theme switcher at the bottom of the rail.

**Architecture:** Fix a Svelte template-reactivity bug by referencing the reactive `activeId` directly in markup (two files). Extract the existing theme apply-logic out of `Settings/General.svelte` into a shared, SSR-guarded `lib/utils/theme.ts` (single source of truth), then build a `ThemeSwitcher` component on top of it and mount it in the desktop rail.

**Tech Stack:** SvelteKit + TypeScript, Tailwind CSS, Vitest (node environment), existing `theme` writable store in `$lib/stores`.

---

## Background / spec

Spec: `docs/superpowers/specs/2026-06-21-rail-highlight-theme-switcher-design.md`.

**Verified ground truth (do not re-discover):**

- The frozen-highlight bug exists in exactly two files: `src/lib/components/app/AppSidebar.svelte` and `src/lib/components/app/MobileRailDrawer.svelte`. No other component has this bug class. Cause: `activeId` is reactive (`$:`), but the template calls a helper `isActive(item)` whose body reads `activeId` — Svelte only tracks identifiers *named in the template expression* (`isActive`, `item`), so it never re-runs on navigation. The rail mounts once and never remounts, so the highlight freezes at first load.
- Theme apply-logic lives in `Settings/General.svelte` `applyTheme()` (lines ~126–186) and `themeChangeHandler()` (lines ~188–192). In that file, the `theme` store import (line 7) is used only at line 189, and the `themes` array (line 17) only at line 140 — both become removable after extraction.
- `src/app.html` (pre-hydration FOUC bootstrap) **must not change**.
- `window.applyTheme` is a never-defined external hook (Electron). Preserve the guarded call; it has no TypeScript declaration, so cast it locally.
- Vitest runs in the **node** environment (no jsdom, no `@testing-library/svelte`). Only pure logic is unit-testable. Modules that import `$lib/stores` are importable in tests. `src/lib/utils/` is the correct home for the new util + its test.

**Out of scope (explicit decisions, not omissions):**

- `src/routes/+layout.svelte` contains a third theme path — an Electron `theme:update` handler (~lines 785–803) that duplicates the class-toggling. It is **not** refactored here (the Electron path can't be exercised in local verification). A follow-up could adopt `setTheme`/`applyTheme` there.
- No theme switcher in `MobileRailDrawer.svelte` (mobile drawer keeps only the highlight fix).

## File structure

**New**
- `src/lib/utils/theme.ts` — `THEME_LIST`, `prefersSystemDark()`, `resolveMode()` (pure), `applyTheme()`, `setTheme()`.
- `src/lib/utils/theme.test.ts` — vitest unit test for the pure `resolveMode` + `THEME_LIST`.
- `src/lib/components/icons/Sun.svelte`, `src/lib/components/icons/Moon.svelte` — icon components matching the existing convention.
- `src/lib/components/app/ThemeSwitcher.svelte` — the rail switcher (collapsed icon toggle + expanded pill).

**Modified**
- `src/lib/components/app/AppSidebar.svelte` — highlight fix + mount `ThemeSwitcher`.
- `src/lib/components/app/MobileRailDrawer.svelte` — highlight fix.
- `src/lib/components/chat/Settings/General.svelte` — consume the shared module.

## Testing strategy (read before starting)

The repo has **no Svelte component test runner** — only vitest in node for pure logic. Therefore:

- The pure `resolveMode` function is covered by a real vitest unit test (Task 2).
- All Svelte/DOM behavior (the highlight reactivity, the switcher UI, the Settings dropdown) is verified by `npm run check` (svelte-check, must pass) **plus** a concrete dev-server checklist. This is the repo's reality, not a placeholder — do not scaffold jsdom/testing-library to invent component tests.

Commands used throughout:
- Type check: `npm run check`
- Unit test (single file): `npm run test:frontend -- --run src/lib/utils/theme.test.ts`
- Dev server: `npm run dev` then open the printed local URL (e.g. `http://localhost:5173`).

---

## Task 1: Fix the frozen rail highlight (both rails)

One coherent fix applied to both files: drop the `isActive` helper and compare `item.id === activeId` directly in the template so Svelte tracks `activeId` as a dependency. No unit test is possible (pure template-reactivity bug, no component runner) — verified via `npm run check` + dev server.

**Files:**
- Modify: `src/lib/components/app/AppSidebar.svelte` (lines 10, 20, 65, 67)
- Modify: `src/lib/components/app/MobileRailDrawer.svelte` (lines 11, 39, 75, 77)

- [ ] **Step 1: Edit `AppSidebar.svelte` — drop the unused `RailItem` import**

Change line 10 from:

```svelte
	import { railItems, activeRailItem, type RailItem } from './railItems';
```

to:

```svelte
	import { railItems, activeRailItem } from './railItems';
```

- [ ] **Step 2: Edit `AppSidebar.svelte` — delete the `isActive` helper**

Delete line 20 entirely:

```svelte
	const isActive = (item: RailItem) => item.id === activeId;
```

(Keep line 18: `$: activeId = activeRailItem($page.url.pathname, visibleItems)?.id;`)

- [ ] **Step 3: Edit `AppSidebar.svelte` — reference `activeId` directly in markup**

Replace the anchor's reactive attributes (currently lines 62–70) so both `isActive(item)` calls become `item.id === activeId`:

```svelte
					<a
						href={item.href}
						aria-label={$i18n?.t(item.label) ?? item.label}
						aria-current={item.id === activeId ? 'page' : undefined}
						class="flex items-center h-9 rounded-lg transition-colors duration-100
							{item.id === activeId
								? 'bg-gray-200/60 dark:bg-gray-900 text-gray-900 dark:text-white'
								: 'text-gray-600 dark:text-gray-400 hover:bg-gray-200/40 dark:hover:bg-gray-900/60 hover:text-gray-900 dark:hover:text-white'}"
					>
```

- [ ] **Step 4: Edit `MobileRailDrawer.svelte` — drop the unused `RailItem` import**

Change line 11 from:

```svelte
	import { railItems, activeRailItem, type RailItem } from './railItems';
```

to:

```svelte
	import { railItems, activeRailItem } from './railItems';
```

- [ ] **Step 5: Edit `MobileRailDrawer.svelte` — delete the `isActive` helper**

Delete line 39 entirely:

```svelte
	const isActive = (item: RailItem) => item.id === activeId;
```

(Keep line 19: `$: activeId = activeRailItem($page.url.pathname, visibleItems)?.id;`)

- [ ] **Step 6: Edit `MobileRailDrawer.svelte` — reference `activeId` directly in markup**

Replace the anchor's reactive attributes (currently lines 73–80) so both `isActive(item)` calls become `item.id === activeId`:

```svelte
					<a
						href={item.href}
						aria-current={item.id === activeId ? 'page' : undefined}
						class="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition
							{item.id === activeId
							? 'bg-gray-100 dark:bg-gray-800 text-black dark:text-white font-medium'
							: 'text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-850'}"
					>
```

- [ ] **Step 7: Type check**

Run: `npm run check`
Expected: PASS (no new errors in `AppSidebar.svelte` or `MobileRailDrawer.svelte`; no "unused `RailItem`" / "unused `isActive`" warnings).

- [ ] **Step 8: Verify in the dev server**

Run: `npm run dev`, open the printed URL, log in.
Click through the rail items (Home → Osool AI → Notes → Workspace → Policy Review → Admin, whichever are visible for your user). Expected: the highlighted (active) item changes to match the page you are on for every navigation — it no longer stays stuck on the item that was active at first load.

- [ ] **Step 9: Commit**

```bash
git add src/lib/components/app/AppSidebar.svelte src/lib/components/app/MobileRailDrawer.svelte
git commit -m "fix(rail): track active item reactively so highlight follows route"
```

---

## Task 2: Shared theme module `lib/utils/theme.ts` (TDD on the pure part)

Create the single-source-of-truth theme module. TDD the pure `resolveMode`; the DOM-mutating `applyTheme`/`setTheme` are SSR-guarded ports of the existing logic (verified by type check + later manual runs, since they can't run in node).

**Files:**
- Create: `src/lib/utils/theme.ts`
- Test: `src/lib/utils/theme.test.ts`

- [ ] **Step 1: Write the failing test**

Create `src/lib/utils/theme.test.ts`:

```ts
import { describe, it, expect } from 'vitest';

import { resolveMode, THEME_LIST } from './theme';

describe('resolveMode', () => {
	it('returns light for the light theme regardless of OS preference', () => {
		expect(resolveMode('light', false)).toBe('light');
		expect(resolveMode('light', true)).toBe('light');
	});

	it('returns dark for dark and oled-dark', () => {
		expect(resolveMode('dark', false)).toBe('dark');
		expect(resolveMode('oled-dark', false)).toBe('dark');
	});

	it('resolves system from the OS preference', () => {
		expect(resolveMode('system', true)).toBe('dark');
		expect(resolveMode('system', false)).toBe('light');
	});

	it('treats any unknown theme as dark', () => {
		expect(resolveMode('whatever', false)).toBe('dark');
	});
});

describe('THEME_LIST', () => {
	it('lists every theme class applyTheme manages', () => {
		expect(THEME_LIST).toEqual(['dark', 'light', 'oled-dark']);
	});
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test:frontend -- --run src/lib/utils/theme.test.ts`
Expected: FAIL — cannot resolve `./theme` (module does not exist yet).

- [ ] **Step 3: Implement `src/lib/utils/theme.ts`**

Create `src/lib/utils/theme.ts`. This is the existing `General.svelte` `applyTheme` ported verbatim except: SSR guards added, the local `themes` array replaced by the exported `THEME_LIST`, `window.matchMedia` reads routed through `prefersSystemDark()`, the never-typed `window.applyTheme` hook narrow-cast, and the debug `console.log` lines dropped.

```ts
import { theme as themeStore } from '$lib/stores';

/**
 * Every theme class name applyTheme may add to <html>, so the stale ones can
 * be stripped before applying the active theme. Single source of truth shared
 * by Settings/General.svelte and the rail ThemeSwitcher.
 */
export const THEME_LIST = ['dark', 'light', 'oled-dark'];

/** True when the OS prefers a dark color scheme. SSR-safe (false on the server). */
export function prefersSystemDark(): boolean {
	return typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches;
}

/**
 * Collapse a stored theme to the light/dark mode that is *effectively* showing:
 * 'system' resolves via the OS preference, 'oled-dark' counts as 'dark'. Pure so
 * it can be unit-tested without a DOM.
 */
export function resolveMode(theme: string, systemPrefersDark: boolean): 'light' | 'dark' {
	if (theme === 'system') {
		return systemPrefersDark ? 'dark' : 'light';
	}
	return theme === 'light' ? 'light' : 'dark';
}

/**
 * Apply a theme to the document: toggle the <html> classes, restore the gray
 * CSS variables (the part that separates plain Dark from OLED), and update the
 * meta theme-color. Ported from Settings/General.svelte with SSR guards added.
 * No-op during SSR.
 */
export function applyTheme(_theme: string): void {
	if (typeof document === 'undefined') {
		return;
	}

	let themeToApply = _theme === 'oled-dark' ? 'dark' : _theme;

	if (_theme === 'system') {
		themeToApply = prefersSystemDark() ? 'dark' : 'light';
	}

	if (themeToApply === 'dark' && !_theme.includes('oled')) {
		document.documentElement.style.setProperty('--color-gray-800', '#333');
		document.documentElement.style.setProperty('--color-gray-850', '#262626');
		document.documentElement.style.setProperty('--color-gray-900', '#171717');
		document.documentElement.style.setProperty('--color-gray-950', '#0d0d0d');
	}

	THEME_LIST.filter((e) => e !== themeToApply).forEach((e) => {
		e.split(' ').forEach((cls) => {
			document.documentElement.classList.remove(cls);
		});
	});

	themeToApply.split(' ').forEach((cls) => {
		document.documentElement.classList.add(cls);
	});

	const metaThemeColor = document.querySelector('meta[name="theme-color"]');
	if (metaThemeColor) {
		if (_theme.includes('system')) {
			const systemTheme = prefersSystemDark() ? 'dark' : 'light';
			metaThemeColor.setAttribute('content', systemTheme === 'light' ? '#ffffff' : '#171717');
		} else {
			metaThemeColor.setAttribute(
				'content',
				_theme === 'dark' ? '#171717' : _theme === 'oled-dark' ? '#000000' : '#ffffff'
			);
		}
	}

	if (typeof window !== 'undefined') {
		const externalApplyTheme = (window as unknown as { applyTheme?: () => void }).applyTheme;
		if (externalApplyTheme) {
			externalApplyTheme();
		}
	}

	if (_theme.includes('oled')) {
		document.documentElement.style.setProperty('--color-gray-800', '#101010');
		document.documentElement.style.setProperty('--color-gray-850', '#050505');
		document.documentElement.style.setProperty('--color-gray-900', '#000000');
		document.documentElement.style.setProperty('--color-gray-950', '#000000');
		document.documentElement.classList.add('dark');
	}
}

/**
 * Persist and apply a theme: update the store, write localStorage, mutate the
 * document. The single entry point used by both the Settings dropdown and the
 * rail switcher so they can never drift.
 */
export function setTheme(theme: string): void {
	themeStore.set(theme);
	if (typeof localStorage !== 'undefined') {
		localStorage.setItem('theme', theme);
	}
	applyTheme(theme);
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm run test:frontend -- --run src/lib/utils/theme.test.ts`
Expected: PASS (6 assertions across the two describe blocks).

- [ ] **Step 5: Type check**

Run: `npm run check`
Expected: PASS (no errors in `theme.ts`).

- [ ] **Step 6: Commit**

```bash
git add src/lib/utils/theme.ts src/lib/utils/theme.test.ts
git commit -m "feat(theme): add shared theme module (applyTheme/setTheme/resolveMode)"
```

---

## Task 3: Refactor `Settings/General.svelte` to use the shared module

Remove the now-duplicated apply-logic from `General.svelte` and route the dropdown through `setTheme`. All four modes (System / Dark / OLED Dark / Light) must keep working.

**Files:**
- Modify: `src/lib/components/chat/Settings/General.svelte` (lines 7, 17, 126–192, 209)

- [ ] **Step 1: Add the shared-module import**

After the existing store import (line 7), add a new import line:

```svelte
	import { setTheme } from '$lib/utils/theme';
```

- [ ] **Step 2: Drop the now-unused `theme` store import**

Change line 7 from:

```svelte
	import { config, models, settings, theme, user } from '$lib/stores';
```

to:

```svelte
	import { config, models, settings, user } from '$lib/stores';
```

(`theme` was used only inside the `themeChangeHandler` being removed below.)

- [ ] **Step 3: Delete the local `themes` array**

Delete line 17:

```svelte
	let themes = ['dark', 'light', 'oled-dark'];
```

(It was used only by the local `applyTheme` being removed. The dropdown `<option>`s are hard-coded and do not reference it.)

- [ ] **Step 4: Delete the local `applyTheme` and `themeChangeHandler`**

Delete the entire `const applyTheme = (_theme: string) => { ... };` block (currently lines ~126–186) **and** the `const themeChangeHandler = (_theme: string) => { ... };` block (currently lines ~188–192):

```svelte
	const themeChangeHandler = (_theme: string) => {
		theme.set(_theme);
		localStorage.setItem('theme', _theme);
		applyTheme(_theme);
	};
```

Keep `selectedTheme` (line 18) and its `onMount` initialization (line 111: `selectedTheme = localStorage.theme ?? 'system';`).

- [ ] **Step 5: Point the dropdown at `setTheme`**

In the theme `<select>` (currently line 209), change:

```svelte
						on:change={() => themeChangeHandler(selectedTheme)}
```

to:

```svelte
						on:change={() => setTheme(selectedTheme)}
```

- [ ] **Step 6: Type check**

Run: `npm run check`
Expected: PASS (no "unused `theme`", no "`applyTheme` is not defined", no "`themeChangeHandler` is not defined" errors).

- [ ] **Step 7: Verify in the dev server**

Run: `npm run dev`, open Settings → General. Switch the Theme dropdown through **System**, **Dark**, **OLED Dark**, **Light**. Expected: each applies correctly (page colors change; OLED is pure black; System follows your OS), and a reload preserves the choice (persisted to `localStorage.theme`).

- [ ] **Step 8: Commit**

```bash
git add src/lib/components/chat/Settings/General.svelte
git commit -m "refactor(settings): use shared theme module for theme switching"
```

---

## Task 4: Add `Sun` and `Moon` icon components

Two presentational icon components matching the existing `icons/` convention (`className` + `strokeWidth` props, `stroke="currentColor"`, `fill="none"`). No test (trivial markup); verified by type check and visually in Task 6.

**Files:**
- Create: `src/lib/components/icons/Sun.svelte`
- Create: `src/lib/components/icons/Moon.svelte`

- [ ] **Step 1: Create `Sun.svelte`**

```svelte
<script lang="ts">
	export let className = 'size-4';
	export let strokeWidth = '1.5';
</script>

<svg
	aria-hidden="true"
	xmlns="http://www.w3.org/2000/svg"
	fill="none"
	viewBox="0 0 24 24"
	stroke-width={strokeWidth}
	stroke="currentColor"
	class={className}
>
	<path
		stroke-linecap="round"
		stroke-linejoin="round"
		d="M12 3v2.25m6.364.386-1.591 1.591M21 12h-2.25m-.386 6.364-1.591-1.591M12 18.75V21m-4.773-4.227-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z"
	/>
</svg>
```

- [ ] **Step 2: Create `Moon.svelte`**

```svelte
<script lang="ts">
	export let className = 'size-4';
	export let strokeWidth = '1.5';
</script>

<svg
	aria-hidden="true"
	xmlns="http://www.w3.org/2000/svg"
	fill="none"
	viewBox="0 0 24 24"
	stroke-width={strokeWidth}
	stroke="currentColor"
	class={className}
>
	<path
		stroke-linecap="round"
		stroke-linejoin="round"
		d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.636 7.364 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z"
	/>
</svg>
```

- [ ] **Step 3: Type check**

Run: `npm run check`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/icons/Sun.svelte src/lib/components/icons/Moon.svelte
git commit -m "feat(icons): add Sun and Moon icons"
```

---

## Task 5: Build the `ThemeSwitcher` component

The rail switcher: a single icon toggle when the rail is collapsed, and a 2-segment Light/Dark pill when expanded. The active segment is derived reactively from `$theme` via `resolveMode`. Clicking writes a plain `light`/`dark` mode through `setTheme`. The collapsed/expanded swap uses the rail's existing `group/rail` hover state with `group-hover/rail:hidden` / `hidden group-hover/rail:flex` (a display swap is required, not opacity — the full pill cannot fit in the 57px collapsed width).

**Files:**
- Create: `src/lib/components/app/ThemeSwitcher.svelte`

- [ ] **Step 1: Create `ThemeSwitcher.svelte`**

```svelte
<script lang="ts">
	import { getContext } from 'svelte';

	import { theme } from '$lib/stores';
	import { setTheme, resolveMode, prefersSystemDark } from '$lib/utils/theme';

	import Sun from '$lib/components/icons/Sun.svelte';
	import Moon from '$lib/components/icons/Moon.svelte';

	const i18n = getContext<any>('i18n');

	// The mode currently showing: 'system' resolves to the OS preference,
	// 'oled-dark' counts as 'dark'. Re-runs whenever $theme changes.
	$: mode = resolveMode($theme, prefersSystemDark());

	const select = (next: 'light' | 'dark') => setTheme(next);
	const toggle = () => select(mode === 'dark' ? 'light' : 'dark');
</script>

<div class="shrink-0 px-2 py-2 border-t border-gray-200/70 dark:border-gray-900">
	<!-- Collapsed: single toggle button (icon = current mode) -->
	<button
		type="button"
		on:click={toggle}
		aria-label={$i18n?.t('Toggle theme') ?? 'Toggle theme'}
		class="flex group-hover/rail:hidden w-full h-9 items-center rounded-lg
			text-gray-600 dark:text-gray-400 hover:bg-gray-200/40 dark:hover:bg-gray-900/60
			hover:text-gray-900 dark:hover:text-white transition-colors duration-100"
	>
		<span class="w-10 shrink-0 flex items-center justify-center">
			{#if mode === 'dark'}
				<Moon className="size-[1.125rem]" strokeWidth="1.5" />
			{:else}
				<Sun className="size-[1.125rem]" strokeWidth="1.5" />
			{/if}
		</span>
	</button>

	<!-- Expanded: 2-segment Light/Dark pill -->
	<div
		role="group"
		aria-label={$i18n?.t('Theme') ?? 'Theme'}
		class="hidden group-hover/rail:flex gap-1 p-1 rounded-lg bg-gray-200/60 dark:bg-gray-900"
	>
		<button
			type="button"
			on:click={() => select('light')}
			aria-pressed={mode === 'light'}
			class="flex-1 flex items-center justify-center gap-1.5 h-7 rounded-md text-[12px] font-medium
				transition-colors duration-100
				{mode === 'light'
					? 'bg-white text-gray-900 shadow-sm'
					: 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'}"
		>
			<Sun className="size-4" strokeWidth="1.5" />
			<span>{$i18n?.t('Light') ?? 'Light'}</span>
		</button>
		<button
			type="button"
			on:click={() => select('dark')}
			aria-pressed={mode === 'dark'}
			class="flex-1 flex items-center justify-center gap-1.5 h-7 rounded-md text-[12px] font-medium
				transition-colors duration-100
				{mode === 'dark'
					? 'bg-gray-700 text-white shadow-sm'
					: 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'}"
		>
			<Moon className="size-4" strokeWidth="1.5" />
			<span>{$i18n?.t('Dark') ?? 'Dark'}</span>
		</button>
	</div>
</div>
```

- [ ] **Step 2: Type check**

Run: `npm run check`
Expected: PASS (no errors in `ThemeSwitcher.svelte`).

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/app/ThemeSwitcher.svelte
git commit -m "feat(rail): add ThemeSwitcher component (collapsed toggle + expanded pill)"
```

---

## Task 6: Mount `ThemeSwitcher` in the desktop rail + full verification

Mount the switcher at the bottom of the rail, directly above the user profile menu, and verify the whole feature end-to-end.

**Files:**
- Modify: `src/lib/components/app/AppSidebar.svelte` (import near line 8; insert block before the `{#if $user ...}` user section at line 87)

- [ ] **Step 1: Import `ThemeSwitcher`**

After the existing `UserMenu` import (line 8), add:

```svelte
	import ThemeSwitcher from './ThemeSwitcher.svelte';
```

- [ ] **Step 2: Mount it above the user menu**

Immediately before the user section (the line `{#if $user !== undefined && $user !== null}`, currently line 87), insert:

```svelte
	<!-- Theme -->
	<ThemeSwitcher />

```

The result is: nav items (`flex-1` scroll area) → `<ThemeSwitcher />` → user profile menu, each as its own bottom-anchored section.

- [ ] **Step 3: Type check**

Run: `npm run check`
Expected: PASS.

- [ ] **Step 4: Verify the switcher in the dev server**

Run: `npm run dev`, open the URL, log in.

1. With the rail **collapsed** (not hovered): a single sun-or-moon icon shows at the bottom above your avatar, reflecting the current theme (moon when dark, sun when light). Click it → the whole app flips light↔dark and the icon updates.
2. **Hover** the rail to expand it: the single icon is replaced by the `☀ Light | ☾ Dark` pill, with the active mode's segment highlighted.
3. Click the inactive segment → theme switches; the highlighted segment moves to match.
4. Open Settings → General: the dropdown reflects the mode you selected from the rail (e.g. after clicking Dark in the rail, the dropdown shows Dark). Conversely, picking a mode in Settings updates the rail switcher's active segment.
5. Reload the page → the chosen theme persists.

- [ ] **Step 5: Re-verify the highlight fix still works**

With the dev server running, navigate between rail items again and confirm the active-item highlight tracks the current route (regression check after mounting the switcher).

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/app/AppSidebar.svelte
git commit -m "feat(rail): mount ThemeSwitcher at the bottom of the desktop rail"
```

---

## Task 7: Final checks

- [ ] **Step 1: Full type check**

Run: `npm run check`
Expected: PASS with no new errors.

- [ ] **Step 2: Run the frontend unit tests**

Run: `npm run test:frontend -- --run src/lib/utils/theme.test.ts`
Expected: PASS.

- [ ] **Step 3: Lint/format the touched files**

Run: `npx prettier --write src/lib/utils/theme.ts src/lib/utils/theme.test.ts src/lib/components/app/ThemeSwitcher.svelte src/lib/components/app/AppSidebar.svelte src/lib/components/app/MobileRailDrawer.svelte src/lib/components/icons/Sun.svelte src/lib/components/icons/Moon.svelte src/lib/components/chat/Settings/General.svelte`
Expected: files formatted (commit any resulting changes).

- [ ] **Step 4: Final manual smoke (one pass)**

In the dev server: (a) navigation highlight follows the route on desktop rail and mobile drawer; (b) rail theme toggle works collapsed and expanded; (c) Settings dropdown still offers all four modes and stays in sync with the rail. Expected: all pass.

- [ ] **Step 5: Commit any formatting changes**

```bash
git add -A
git commit -m "chore(rail): format theme switcher + highlight fix changes"
```
