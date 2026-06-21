# Global rail: highlight fix + theme switcher

**Date:** 2026-06-21
**Status:** Approved — ready for implementation plan

## Problem

The global left rail (`AppSidebar.svelte`) navigates correctly, but its active-item
highlight is wrong: it stays stuck on the page that was active when the app first
loaded instead of following the current route. Separately, the rail has no quick way
to switch between light and dark themes — that lives only in Settings → General behind
a four-option dropdown.

## Goals

1. The rail's active highlight tracks the current route on every navigation.
2. Add a light/dark theme switcher at the bottom of the rail, styled as a 2-segment
   pill (per the user's reference image) when expanded and a single toggle button when
   collapsed.

## Non-goals

- No change to which routes map to which rail item (`railItems.ts` matching is already
  correct).
- No theme switcher in the mobile drawer (the highlight fix still applies there).
- No removal of the existing `System` / `OLED Dark` modes — all four modes remain
  available in Settings → General.

## Root cause of the highlight bug

Both `AppSidebar.svelte` and `MobileRailDrawer.svelte` compute the active item
reactively:

```js
$: activeId = activeRailItem($page.url.pathname, visibleItems)?.id;
const isActive = (item) => item.id === activeId;
```

…but the template calls the **function** `isActive(item)`:

```svelte
aria-current={isActive(item) ? 'page' : undefined}
class="... {isActive(item) ? <active> : <inactive>}"
```

Svelte re-evaluates a template expression only when an identifier *written in that
expression* changes. Here those identifiers are `isActive` (a `const`) and `item` (the
`{#each}` loop variable) — neither changes on navigation. `activeId` is read only
*inside* the function body, which the compiler does not analyze for template
dependencies. The rail is mounted once in the root layout and never remounts, so the
highlight is computed at first render and then frozen.

## Design

### 1. Highlight fix

Drop the `isActive` helper and reference `activeId` directly in the template so Svelte
tracks it as a dependency:

```svelte
aria-current={item.id === activeId ? 'page' : undefined}
class="... {item.id === activeId ? <active> : <inactive>}"
```

Apply to both `AppSidebar.svelte` and `MobileRailDrawer.svelte`. `activeRailItem()` and
`railItems.ts` are unchanged.

### 2. Shared theme module — `lib/utils/theme.ts`

The light/dark apply-logic is currently duplicated (a `~60-line applyTheme` inside
`Settings/General.svelte` plus a copy in `app.html`) with no shared module. Extract a
single source of truth so the switcher and the Settings dropdown cannot drift:

- `applyTheme(theme: string)` — the DOM side, moved verbatim from `General.svelte`:
  toggle `dark`/`light` classes on `documentElement`, restore the `--color-gray-*`
  variables (the part that distinguishes plain Dark from OLED Dark), and set the meta
  `theme-color`.
- `setTheme(theme: string)` — `theme.set(theme)` + `localStorage.theme = theme` +
  `applyTheme(theme)`.
- `resolveMode(theme: string): 'light' | 'dark'` — collapses `system` (via
  `prefers-color-scheme`) and `oled-dark` → `dark`, so the switcher knows which segment
  is active.

`General.svelte`'s `themeChangeHandler` becomes a thin call to `setTheme`. Its local
`themes` list and the four-option dropdown are unchanged; all four modes still work.

### 3. ThemeSwitcher component + icons

- New `lib/components/icons/Sun.svelte` and `lib/components/icons/Moon.svelte`, matching
  the existing icon convention (`className` / `strokeWidth` props).
- New `lib/components/app/ThemeSwitcher.svelte`:
  - Active segment derived from `resolveMode($theme)` (reactive).
  - **Collapsed (~57px):** a single button showing the current effective mode's icon
    (sun = light, moon = dark); clicking it toggles light ↔ dark.
  - **Expanded (~240px):** a 2-segment pill `☀ Light | ☾ Dark` styled to match the
    reference image; clicking a segment sets that mode explicitly via
    `setTheme('light' | 'dark')`.
  - Uses the same `opacity-0 group-hover/rail:opacity-100` reveal pattern as the other
    rail items so it morphs with the rail width.

When the saved theme is `system`, the pill highlights whichever mode is currently
effective; when it is `oled-dark`, the pill highlights `Dark`. Clicking a segment always
writes a plain `light` or `dark` mode (never `oled-dark` / `system`).

### 4. Placement

Mount `ThemeSwitcher` in its own bordered section at the bottom of the desktop rail in
`AppSidebar.svelte`, directly **above** the user profile menu (the profile menu stays
the bottom anchor). Not added to `MobileRailDrawer.svelte`.

## Files

**New**
- `src/lib/utils/theme.ts`
- `src/lib/components/app/ThemeSwitcher.svelte`
- `src/lib/components/icons/Sun.svelte`
- `src/lib/components/icons/Moon.svelte`

**Modified**
- `src/lib/components/app/AppSidebar.svelte` — highlight fix + mount `ThemeSwitcher`
- `src/lib/components/app/MobileRailDrawer.svelte` — highlight fix
- `src/lib/components/chat/Settings/General.svelte` — use shared `setTheme` / `applyTheme`

## Verification

1. Run the dev server.
2. Click through the rail items (Home, Chat, Notes, Workspace, Policy Review, Admin) and
   confirm the highlight tracks the current page on every navigation — not the page that
   was active at load.
3. Toggle the switcher in both collapsed and expanded states; confirm the theme changes
   and the active segment reflects it.
4. Open Settings → General and confirm all four modes (System / Dark / OLED Dark / Light)
   still apply correctly and that picking a mode there updates the rail switcher's
   active segment.
