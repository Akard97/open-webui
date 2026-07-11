# Hub Homepage (v6) — Design

**Date:** 2026-07-11
**Status:** Approved (pending spec review)
**Source of truth for visuals:** `docs/mockups/hub-homepage-v6.html` (+ `v6-light.png` / `v6-dark.png`)

## Goal

Implement the approved v6 mockup as the real `/home` page of the Osool
Intelligence Hub, and make `/home` the default post-login landing page.

## Decisions (locked with user)

| Decision | Choice |
| --- | --- |
| Landing | Login redirects to `/home`; chat stays at `/`. |
| Home at `/` + chat at `/OsoolAI` | **Deferred** — separate later phase (46 call sites, upstream-merge tax). Not in this build. |
| Coming-soon cards | Decorative. Content hardcoded. "Notify me" = no-op success toast. |
| i18n | All visible strings via `$i18n.t()`, English defaults. Date via user locale. |
| Live-card visibility | Always show both live tool cards (Osool AI, WorkOS) to everyone. |

## Scope

### In

1. **`src/routes/(app)/home/+page.svelte`** — full v6 page: framed canvas,
   hero (blueprint grid lines, greeting, constellation viz), tools row
   (Osool AI chat vignette, WorkOS kanban vignette, coming-soon stack),
   footer. Ported from the mockup.
2. **`src/routes/(app)/home/+layout.svelte`** — gutted: `<title>` +
   scroll container only. The current file's Notes/Calendar nav (stale
   upstream leftover pointing at `/playground`) is deleted.
3. **Post-login redirect** — fallback `'/'` → `'/home'` at the two spots in
   `src/routes/auth/+page.svelte` (lines ~63 and ~171). Explicit
   `?redirect=` params keep working unchanged.
4. **Assets** — Vite-bundled imports per the standing logo rule (no
   `/static` URLs): copy `osool-ai-logo-black-transparent.png`,
   `osool-ai-logo-whitish-transparent.png`, `favicon.png`,
   `favicon-dark.png` from `static/static/` into `src/lib/assets/`.
   WorkOS logos imported from existing
   `src/lib/components/workos/assets/`.
5. **Greeting helper** — `src/routes/(app)/home/greeting.ts`: pure
   functions returning discriminant strings — `greetingForHour(h)` →
   `'morning' | 'afternoon' | 'evening'`, `daymarkForHour(h)` →
   `'sun' | 'moon'`, `wishForHour(h)` → `'bright' | 'rest' | 'calm'`.
   The component maps discriminants to i18n keys. Unit-tested (vitest),
   TDD.

### Out

- Rail / mobile drawer changes (mockup's rail is context only; the app
  already renders `AppSidebar`).
- Mockup's `.mockbar` theme toggle and its theme script (app has its own
  theme system; page follows the `.dark` class on `<html>`).
- Functional notify-me backend, config-driven coming-soon cards.
- Moving chat off `/`.

## Architecture

Single page component (Approach A). The page is ~90% static presentation;
mockup CSS ports nearly verbatim into the Svelte `<style>` block (scoped).
If a chunk becomes unreadable, extract a dumb presentational child into
`src/lib/components/home/` (candidates: `HeroViz.svelte`,
`ComingSoonCard.svelte`) — no data-driven card system.

### CSS strategy

- Local semantic vars (`--sun-*`, `--wash`, `--tint`, `--accent`, shadows,
  etc.) declared on the page wrapper; dark overrides under
  `:global(.dark)` ancestry. Values reference the existing global ramps
  (`--color-brand-*`, `--color-gray-*` from `src/tailwind.css`) instead of
  redefining raw oklch numbers, except the v6-only sun/amber layer which
  is new.
- All keyframes (`fadeUp`, `floaty`, `dashmove`, `blip`, `shimmer`,
  `stripes`, `draw`), `color-mix()` washes, blueprint grid backgrounds,
  shimmer skeletons kept as-is.
- `prefers-reduced-motion` block kept.
- Logical properties (`inset-inline-end`, `margin-inline-start`) kept —
  RTL-safe.
- Fonts: app already loads Inter/Archivo (`src/app.css`); headings use the
  app's `font-primary` convention (Archivo).

### Dynamic behavior

- **Greeting bucket:** `h < 12` morning, `< 17` afternoon, else evening.
- **Day mark:** moon when `h >= 19 || h < 6`, else sun.
- **Footer wish:** morning → "have a bright {weekday}", afternoon →
  "enjoy the rest of your {weekday}", evening → "have a calm evening".
- **Name:** first whitespace-separated token of `$user.name`; if absent,
  greeting renders without the name span (no dangling comma).
- **Date:** `toLocaleDateString($i18n.language, { weekday, month, day })`.
- **Reveal-on-scroll:** IntersectionObserver in `onMount`, disconnected on
  destroy.
- **Links:** Osool AI "Open" → `/`; WorkOS "Open" → `/workos`.
  "Notify me" → `toast.success($i18n.t("We'll let you know when it's ready."))`.
- **Vignette copy** (chat Q/A, kanban card titles, chip texts) is visible
  text → also through `$i18n.t()`.

## Error handling

No data fetching on this page — nothing to fail. Degenerate states:
missing `$user.name` (handled above), missing i18n keys (i18next falls
back to the key's English default), reduced motion (CSS block).

## Testing

- **Unit:** `greeting.test.ts` — bucket boundaries (0, 6, 11, 12, 16, 17,
  19, 23) for greeting/wish/daymark.
- **Static:** `npm run check` (svelte-check) clean for touched files.
- **Browser smoke** (user's Vite hot-reload server; ask before starting
  any server per standing rule): light + dark, hero renders with real
  name/date, animations run, reveal triggers, Open links navigate,
  Notify me toasts, no console errors, narrow-viewport check
  (≤1020px and ≤760px breakpoints).

## Risks

- Svelte scoping can drop styles for elements only created via `{#each}`
  /conditional markup — mitigated by porting markup 1:1 and checking
  compiled warnings for unused CSS selectors.
- oklch/`color-mix` are already used by the app's stack (Tailwind 4), no
  browser-support concern beyond what the app already requires.
