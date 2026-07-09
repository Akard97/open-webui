# WorkOS Design System — Token Spec & Remediation Plan

**Date:** 2026-07-09
**Status:** Approved decisions, not yet implemented
**Input:** Full design audit of all 62 WorkOS components (6 parallel area audits + repo-wide token census). Audit artifact: https://claude.ai/code/artifact/c1f0c2f1-a555-47c3-9fd4-91a2d7018336

## 1. Problem

WorkOS has exactly one shared design decision (`src/lib/components/workos/lib/colors.ts`) and ~61 components improvising in raw Tailwind:

- 21 distinct text sizes (incl. fractional `text-[13.5px]`, `[12.5px]`, `[11.5px]`, `[10.5px]`)
- 1,001 raw `gray-*` refs; `text-muted-foreground` / `border-border` / `bg-card`: 0 uses
- `focus-visible`: 0 occurrences in all of WorkOS
- "Done" rendered in 6 greens, "overdue" in 3 reds, brand in 2 teals + sky strays
- 7 radii with no assignment rule; 3 status-pill anatomies; 4 avatar systems; 3 progress bars; 2 unscheduled rails; 3 drag/drop affordances
- shadcn adopted in 18/62 files; `Button`/`Input`/`Checkbox`/`Badge`/`Avatar`/`Table` installed but bypassed

## 2. Locked decisions (2026-07-09)

| # | Decision | Choice |
|---|---|---|
| D1 | Brand accent | **Keep the light/dark `--primary` split** — light = Pantone 309 C (deep teal), dark = 3125 C (#00a5ba). UI accents must use the token (`text-primary`, `bg-primary`), never hardcoded `#00a5ba`. Status color `in_progress: #00a5ba` stays as a *data* color (theme-independent), which is a different role from the UI accent. Unread indicators switch from `sky-500` to the primary token. |
| D2 | Done/positive green | **#769a4a** (Pantone 576, = existing `STATUS_COLOR.done` and `--color-success`). Replaces #5DCAA5, #16a34a, green-700, emerald-600, and the teal "completed" chart series. |
| D3 | Warm hue assignment | **amber-500 #f59e0b = time pressure (due soon)**; **#d97706 = in-review status + health at-risk**; **orange-600 #ea580c = priority high + health behind**. Replaces #f0b47a. One meaning per hue. |
| D4 | Ink hero | **Retire.** The dark KPI panel on Overview (`KpiBand`) becomes a standard themed card like its siblings. Its ~14 hardcoded hexes are deleted, not tokenized. Boldness budget moves to the display-numeral + delta system. |
| D5 | Tab paradigms | **Codify both:** underline tabs (`border-b-2` active) = navigating sections (Topbar workstream tabs, Admin tabs — admin active tab also gains `text-primary`); pill segments (`rounded-full` group) = view options on the same data (Calendar Month/Week, Timeline zoom, My Work Assigned/Created). |

## 3. Token layer (Phase 1 — pure addition, no visual change)

Location: extend `src/lib/components/workos/styles.css` (`.workos-root` scope) + keep `lib/colors.ts` as the TS source of truth. CSS vars mirror the TS values so both Svelte logic and classes read one source.

### 3.1 Semantic color

```css
.workos-root {
  /* data colors — theme-independent, mirror colors.ts */
  --wos-status-backlog: #9ca3af;
  --wos-status-todo: #6b7280;
  --wos-status-in-progress: #00a5ba;
  --wos-status-in-review: #d97706;
  --wos-status-done: #769a4a;
  --wos-status-canceled: #9ca3af;   /* TODO D-followup: distinct hue or hatch — backlog collision */
  --wos-priority-urgent: #dc2626;
  --wos-priority-high: #ea580c;
  --wos-priority-medium: #ca8a04;
  --wos-priority-low: #6b7280;
  --wos-priority-none: #9ca3af;     /* kills #cbd5e1 slate stray + gray-300 text */

  /* outcome semantics */
  --wos-done: #769a4a;              /* D2 */
  --wos-danger: #dc2626;            /* dark pair: #f87171 */
  --wos-due: #f59e0b;               /* D3 due-soon */
  --wos-warn: #d97706;              /* D3 review/at-risk */
  --wos-behind: #ea580c;            /* D3 high/behind */

  /* health map — single source, replaces TaskCard HEALTH_BAR vs HoverCard HEALTH_HEX drift */
  --wos-health-on-track: var(--wos-done);
  --wos-health-at-risk: var(--wos-warn);
  --wos-health-behind: var(--wos-behind);
  --wos-health-overdue: var(--wos-danger);
}
```

Surfaces/borders/hover (light ↔ dark pairs, applied via `dark:` or paired vars):

| Token | Light | Dark | Replaces |
|---|---|---|---|
| `--wos-canvas` | gray-50 | gray-950 | per-view drift (Calendar/List/Overview were gray-900) |
| `--wos-card` | white | gray-900 | ad-hoc card surfaces |
| `--wos-border` | gray-200 | gray-800 | gray-100/200/300 lottery |
| `--wos-hairline` | gray-100 | gray-900 | row dividers |
| `--wos-hover` | gray-50 | gray-850 | gray-50 / /60 / /70 / gray-100 / 850-900 alternation |

Tint recipe — one helper, kills `{hex}24` vs `{hex}1f` vs `bg-*-100` drift:

```ts
// lib/colors.ts
export const tint = (c: string) => `color-mix(in srgb, ${c} 14%, transparent)`;
```

### 3.2 Type ramp — 21 sizes → 7 steps

| Step | Size/weight | Use | Absorbs |
|---|---|---|---|
| `micro` | 10px / 600 | dense chart labels only | [8px] [9px] [10px] [10.5px] |
| `caption` | 11px / 500 | chips, timestamps, table headers | [11px] [11.5px] [12px] [12.5px] |
| `meta` | 12px (`text-xs`) | secondary rows, metadata | `text-xs` vs `[12px]` duplication |
| `body` | 13px / 400–500 | UI body, dialog labels | [13px] [13.5px] |
| `title` | 14px (`text-sm`) / 600 | row titles, buttons | [15px] card titles |
| `heading` | 17px / 650 | view + dialog titles | base/lg/[16px]/[17px] mix |
| `display` | 28px / 700, `tabular-nums tracking-tight` | ALL KPI numerals | [16px]/[22px]/[34px] trio; drop `font-mono` sub-labels |

Implement as `.wos-*` utility classes in `styles.css` (scoped, no global Tailwind theme change).

### 3.3 Radius / elevation / motion / focus contracts

- **Radius:** controls & inputs `rounded-lg` · chips/pills `rounded-full` · cells/swatches `rounded-md` · cards `rounded-xl` · overlays/dialogs `rounded-2xl`. Bare `rounded` and `rounded-[3px]` are banned.
- **Elevation:** 0 = card, border only · 1 = `hover:shadow-md` lift · 2 = popover/hovercard `shadow-xl` (already consistent) · 3 = modal `shadow-2xl`. Nothing else.
- **Motion:** `transition-colors duration-150` on every hoverable; `duration-200 ease-out` for transform/layout. One drag ghost (40% opacity) and one drop affordance (2px `ring-primary` inset + `bg-primary/10`) shared by board/calendar/timeline.
- **Focus:** `focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none` on every interactive element. Currently zero anywhere — single biggest a11y win.

## 4. Shared primitives (Phase 2)

Build in `src/lib/components/workos/ui/`, migrate view by view. Each lands with the deletion of its duplicates.

| Primitive | Replaces | Notes |
|---|---|---|
| `StatusBadge` | 3 pill anatomies (Board/List/Hover) | `size: sm\|md`; StatusDot inside; tint via `tint()` |
| `PriorityFlag` | 4 renderings + lowercase enum in Pills | shared `PRIORITY_LABEL` map; delete dead `commandcenter/PriorityIcon.svelte` |
| `ProgressBar` | 3 anatomies; ProgressCell ignoring health | health-aware fill from `--wos-health-*` |
| `Avatar` (one) | `AssigneeAvatars` + `commandcenter/Avatar` + hand-rolled spans | extend shadcn `ui/avatar` with color-hash fallback from `store.ts LABEL_PALETTE`; `ring-background` not `ring-white` |
| `LabelChip` | 4 variants | `rounded-full`, caption type step |
| `SectionHeader` | drawer-panel drift, uppercase outlier | 13px medium + optional icon |
| `EmptyState` | Timeline-rich vs Calendar-bare spread | icon + line + optional CTA; one placeholder glyph (em-dash) |
| `KpiNumeral` + `DeltaBadge` | 3 numeral styles + 3 delta treatments | `display` type step; up/down = `--wos-done`/`--wos-danger` |
| `NotificationRow` | InboxView vs My Work rail divergence | one hover + unread affordance (primary dot) |
| `UnscheduledItem` (+ rail shell) | calendar `UnscheduledRail` vs timeline `UnscheduledPanel` | one width, header, chip, DnD hookup |

Adoption sweeps: shadcn `Button`/`Input`/`Checkbox` everywhere hand-rolled today; `ModalHost` → shadcn `Dialog`; `FilterBar` menus → `DropdownMenu.CheckboxItem`; `TeamSwitcher` drops its second hand-rolled dropdown; `RulesTab` toast → svelte-sonner.

## 5. Bug fixes to fold into Phase 1 (found during audit)

1. `TaskDetail.svelte:32-37` — local `statusShape()` maps `in_review → 'ring'`; `colors.ts` says `'half'`. Import from `colors.ts`; delete local copies of `STATUS_COLOR` in `TaskDetail`, `BoardView` (`STATUS_META`), `TaskCard` (`PRIORITY_META`).
2. `commandcenter/PriorityIcon.svelte` — dead code, delete.
3. `DistributionCard.svelte` — backlog & canceled share `#9ca3af` (indistinguishable slices); medium/low priorities uncolored.
4. `InboxView.svelte:13-15` — "Mark all read" renders enabled on empty inbox.
5. `RulesTab.svelte` — no loading state; hand-rolled toast.
6. `Topbar.svelte:32,44,45` — `aria-disabled` controls keep hover styles.

## 6. Migration order & verification

Order: tokens+bugs → board → list → detail drawer → My Work/Inbox → Overview (incl. D4 ink retirement) → calendar/timeline → admin → chrome/dialogs.

Verification greps (run per phase; targets at completion):

```
rg -o 'text-\[[0-9.]+px\]' src/lib/components/workos | wc -l   # → 0 (micro step excepted via .wos-micro)
rg -o 'focus-visible' src/lib/components/workos | wc -l         # → >0 per interactive component
rg '#(5DCAA5|16a34a|f0b47a|f27d72|cbd5e1|c9cfd7)' src/lib/components/workos  # → no hits
rg 'sky-500' src/lib/components/workos                          # → no hits
rg -o 'rounded(-\[3px\])?(\s|")' src/lib/components/workos      # bare/3px → 0
```

Per user preference (workos-design-taste): show mockups before coding any visual change — especially the KpiBand retirement (D4) and StatusBadge/ProgressBar consolidation.
