# Policy Review — Overview page polish (design)

**Date:** 2026-06-19
**Status:** Approved (direction A — "cohesive house-style")
**Scope:** Visual polish of a single view. No behaviour change.

## Problem

The Policy Review **Overview** page (`OverviewView.svelte`) reads as plain: three
flat bordered cards under a small welcome header. The same app already ships a
much more polished **Library** page (`AllPoliciesView.svelte`, the `.pl-*`
styles) with a brand accent strip, an eyebrow + hero, a stats band, and
function-colored cards. The two pages feel like they belong to different
products. The page *concept* is good — it just needs to be lifted to the
Library's level of finish so the tool feels consistent.

## Goal

Make Overview look finished and consistent with the Library page, while
keeping its exact layout, copy, navigation, and permission behaviour. A pure
visual lift — a reviewer/approver should notice it looks better, not that
anything moved.

## Non-goals

- No new backend, API, or data sources.
- No restructure of the page (the "Action workspace" and "Editorial" variations
  were considered and set aside).
- No changes to other views, the sidebar, topbar, or shared chrome.
- No copy rewrites.

## Affected files

- `src/lib/components/policy-review/views/OverviewView.svelte` — markup + its
  scoped `<style>` block. This is the only file that changes.
- `src/lib/components/policy-review/styles.css` — **read-only reference** for the
  existing tokens and patterns reused below. Touch only if a needed token/helper
  is genuinely missing (none expected).

## Design (Variation A — cohesive house-style)

The page keeps its structure: header → `My reviews` → `Awaiting your approval`
→ `Recently published`. Each element below is a polish layer, not a
re-architecture.

### 1. Brand accent strip
Add the existing 2px teal→olive gradient strip (the `.pl-brand-line`
treatment) at the very top of the page, so Overview and Library share the same
signature opening.

### 2. Header
Add a mono, uppercase, letter-spaced eyebrow above the existing headline:
`POLICY REVIEW · DASHBOARD` (mirrors `.pl-eyebrow` / `.cp-eyebrow`). Keep the
existing "Welcome back, {firstName}" headline and the existing subtitle copy
unchanged.

### 3. Stats band
A thin inline band directly under the header, hairline-dot separated, mirroring
`.pl-hero-stats`. Each stat is **derived from stores already imported into the
component** and **gated by the same permissions that already gate the cards**:

| Stat          | Value source                                         | Shown when      |
|---------------|------------------------------------------------------|-----------------|
| in progress   | count of my open reviews (draft + rejected)          | `$canUseChecker`|
| awaiting you  | `$approvalQueue.length`                              | `$canApprove`   |
| published     | count of approved policies (`POLICIES` approved)     | always          |

A library-only user (no checker/approver rights) therefore sees only the
"published" stat. Hairline-dot separators render only between visible stats.

### 4. Cards
Keep the three sections and all their content. Polish only:
- A small section-accent dot before each heading (teal for My reviews, olive
  for Awaiting approval, deep-teal for Recently published).
- Card radius softened to match `.pl-rc`-era styling.
- Subtle hover affordance on the cards: border darken + lift
  (`--shadow-sm` → `--shadow-md`), matching the Library cards.

### 5. Recently published
Give each published card a function-colored top accent bar plus a gentle hover
lift, reusing the existing function color tokens (`.pl-fn-*` and the `oklch`
function swatches already in `styles.css`). A Finance policy reads indigo, HR
green, IT teal, etc., instead of every card being identical and plain.

### 6. Empty states
Keep the existing empty-state messages verbatim; only align their styling to
the refreshed cards.

## What stays identical

- Section structure (header + three stacked sections) and the max-width
  container.
- All copy.
- All click targets and navigation: `openReview`, `goNewReview`,
  `view.set('my-reviews' | 'approvals' | 'library')`.
- Permission gating logic (`$canUseChecker`, `$canApprove`).
- `scoreOf` / `summarizeReview` usage for row scores.

## Responsive

- The `My reviews` / `Awaiting your approval` pair sits in a two-column grid
  that collapses to one column on narrow widths.
- Recently-published cards keep the existing `auto-fill, minmax(...)` grid.
- The stats band wraps if space is tight.

## Risks / notes

- The stats band is the only net-new element. It introduces no new data, but it
  must respect permission gating so library-only users don't see reviewer/
  approver counts. This is the main thing to get right.
- Colors and shadows must use the existing `.pr-root` tokens so light-mode
  fidelity and `@scope` isolation are preserved; no raw hex outside the existing
  palette.

## Acceptance

- Overview visually matches the Library page's level of finish (brand strip,
  eyebrow, stats band, accented cards).
- No navigation, permission, or data behaviour changes.
- Library-only users see only the "published" stat and the "Recently published"
  section (plus whatever their permissions already allowed).
- No raw hex colors introduced outside the existing token palette.
