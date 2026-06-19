# Policy Review page redesign — overview-first

**Date:** 2026-06-19
**Status:** Approved design, ready for implementation planning
**Scope:** Frontend only — `src/lib/components/policy-review/`

## Problem

The Policy Review detail page (`ReviewView.svelte`) feels compacted and overwhelming. User feedback identified all four of:

1. Too much shown at once — every theme and PRP group is expanded by default, so all ~70 items are visible as one wall to scroll.
2. Visually cramped — tight vertical rhythm, heavy monospace metadata, low whitespace.
3. Too many competing zones — center checklist, a fixed 340px right decision rail, a filter bar, and the host nav all fight for attention.
4. No clear focal point — hard to know where to look first or what to do.

The same page is used by two roles at different stages: a **reviewer** (checker) working through items in `draft`, and an **approver** deciding on a `pending` review. Today it looks identical in every state.

## Goal

An **overview-first** layout: a spacious, state-adaptive summary band on top; the checklist below it, **collapsed by default**, preserving the full three-tier disclosure hierarchy **Theme → PRP Group → Item**. The page adapts its emphasis to review state and viewer role.

No backend, data-model, or scoring changes. This is a presentation-layer rework.

## Background: the data the page renders (no new types needed)

From `lib/types.ts` and `lib/scoring.ts`:

- **Theme** (top tier, T1–T6): `id`, `name`, `weight` (percent), `gate` (boolean), `threshold` (percent).
- **Section = PRP group** (middle tier, PRP1–PRP29): `id`, `theme` (FK to `Theme.id`), `title`, `codes`, `intent`, `items[]`.
- **ChecklistItemDef** (item tier): `id` (e.g. `PRP1-3`), `n` (display number within its PRP group), `text`, `codes`, `assessment` (`auto` | `human`).
- **ItemResult** (in `Review.results`, keyed by item `id`): `result` (`compliant` | `non-compliant` | `human` | `pending`), `comment?`, `ref?` (`{section, quote}` | null), `confidence?`, `reviewed?`, `edited?`. A missing key reads as `pending` via `rOf`.
- **Review**: `id`, `policyMeta`, `checklistVersionId`, `results`, `status` (`draft` | `pending` | `approved` | `rejected`), `approval`, `strengths`, `createdBy`, `createdAt`.
- **ApprovalState**: `status` (`idle` | `pending` | `approved` | `rejected`), `sentAt`, `decidedAt`, `decidedBy`, `note`.
- **ChecklistVersion** (drives rendering + scoring): `themes`, `sections`, `verdictBands` (`{approved: 85, conditional: 70}`), `standards`.
- **`scoreResult = computeScores(version, results)`** returns:
  - `overall` — weight-weighted average of theme `pct` over themes with `total > 0`.
  - `themeRows[]` — each is `Theme & {total, yes, no, human, pending, items, pct}`. `pct = round(yes / (yes + no) * 100)`; **human and pending are held aside and do not affect pct**.
  - `gatesPass` — every `gate` theme has `pct >= threshold`.
  - `verdict` — `{key, label, reason}`; `key` is `draft` while `humanItemsRemain`, else `approved` / `conditional` / `rejected` per `verdictBands` and `gatesPass`.
  - `humanItemsRemain` — any theme has `human > 0` or `pending > 0`; forces verdict `draft` regardless of score.

**Key distinction:** `scoreResult.verdict` is *computed* and is **not** the same as `Review.status` or `ApprovalState.status`. The headline must not conflate them (see State matrix).

Stores: `activeReview`, `activeVersion`, `canUseChecker`, `canApprove`, `canAdmin`, `picked`, `drawerOpen`, `submitModalOpen`. Mutators: `updateItemResult`, `markReviewed`, `replaceDocument`, `submitForApproval`, `approveAndPublish`, `rejectPolicy`, `deleteReview`.

## Design

### Overall layout

A single scrolling column inside `.pr-root`, top to bottom:

1. **Brand gradient line** — 2px `linear-gradient(90deg, #003B4A 0%, #0F5567 35%, #769A4A 100%)`, reusing `.pl-brand-line` from the Library.
2. **Summary band** — full content-width, multi-row (see below).
3. **Filter toolbar** — the four filters + Expand all / Collapse, acting on the checklist.
4. **Checklist** — Theme → PRP Group → Item, collapsed by default.

The fixed 340px right rail (`.review-side`) is **removed**; everything it held moves into the band. The item drawer (`ItemDrawer`) is unchanged in behavior and still slides in over the page.

### The summary band (replaces the old rail + approval banner)

Ordered contents, laid out as a few horizontal rows rather than a narrow vertical stack:

1. **Identity row** — eyebrow `POLICY REVIEW`, `h1` policy name, meta line (`code · version · pages · Reviewed reviewDate · Reviewer: reviewer`), document download link, and a **Replace** button when `canReplace` (`canUseChecker && status in {draft, rejected}`). Only one `VerdictBadge` on the page total (in the decision cluster, not duplicated here).
2. **Decision cluster** — a baseline stat row (echoing `.pl-hero-stats`): the `VerdictBadge`, the large `overall` weighted score (`tabular-nums`, with `%`), mandatory-gate status (`Both pass` in `--ok` vs `Not passing` in `--bad`), issue threshold (**read from `version.verdictBands.approved`**, not a hard-coded "85%"), and pending-human / open-items counts. The state-adaptive **primary action zone** sits at the end of this row.
3. **Score by theme** — six theme mini-rows in a compact horizontal grid (id badge, name, optional `GATE` mini-badge, `pct`, colored fill bar). Color rules unchanged: `fail` when `gate && pct < threshold && total > 0`; `warn` when `pct < 70 && !fail && total > 0`; else neutral.
4. **Top strengths** + **Critical gaps** — a two-up row. Strengths = `activeReview.strengths` with a `+` prefix. Critical gaps = up to five `non-compliant` items sorted by theme rank (T1→T6, unranked last); empty state `No critical gaps remain.` **Each gap is a button** that opens the item in the drawer (and auto-expands its PRP group); respects `locked` (opens read-only when locked).

### State-adaptive behavior

The band's verdict framing, the checklist editability, and the primary action all key off `(Review.status, role)`:

| State · role | Band leads with | Checklist | Primary action |
|---|---|---|---|
| `draft` / `rejected` · checker | Pending-review verdict, score, **progress (resolved/total) + open-items**; for `rejected`, also the quoted rejection `note` | editable (`locked` false) | **Submit for Approval** → `SubmitApprovalModal`. Disabled while `humanItemsRemain` or `approval.status === 'pending'`. Show "Resolve N open items before submitting" when `openCount > 0`. |
| `pending` · approver (`canApprove`) | Decision verdict + score + gates (read-only); "Submitted {sentAt}" | read-only (`locked` true) | **Approve & Publish** (no note) / **Reject** (note required; confirm disabled until non-empty) |
| `pending` · checker (not approver) | "Submitted for approval — awaiting OE approver" + `sentAt` | read-only | none — show disabled/submitted status text |
| `approved` · any | "Approved & published — {decidedAt} by {decidedBy}", recorded decision as the headline | read-only | none (terminal) |
| `rejected` · approver | rejected verdict + "{decidedAt} by {decidedBy}" + quoted `note` | read-only here (no decision buttons; `approval.status` not `pending`) | none |

This **unifies** the old `ApprovalBanner` (rendered as a separate strip above the header) and the rail's Submit button into one action zone in the band.

Notes:
- `locked = status !== 'draft' && status !== 'rejected'`. Editing (`updateItemResult`, Override/Save in drawer, Replace) only works when not locked.
- Admin satisfies both `canUseChecker` and `canApprove`. On a `pending` review, **decision mode wins** (show Approve/Reject), not reviewer mode.
- Approved headline uses the recorded `ApprovalState` decision, not a live recompute, even if results/bands changed since.

### The three-tier checklist

Source of truth: `version.themes` (T1), `version.sections` grouped by `section.theme` (PRP groups), `section.items` (items) — reuse the existing `byTheme` derived map.

- **Tier 1 — Theme heading** (always-visible summary, not itself a collapse toggle): id badge styled by `theme.id.toLowerCase()` (e.g. `.t1`), name, `MANDATORY GATE` tag when `theme.gate`, and the stat line `{pct}% score · {yes}/{total} compliant · [{human} human] · {weight}% weight` from the matching `themeRows` row. Hidden when no sections under it pass the active filter (`themeHasVisible`).
- **Tier 2 — PRP group row** (the collapsible control; `<button>` with `aria-expanded`/`aria-controls`): rotating chevron, `sec.id · sec.codes`, `sec.title`, `sec.intent`, and right-side minibadges (compliant / non-compliant / human, each shown only when its count > 0). **Collapsed by default.**
- **Tier 3 — Item row**: number rendered as `sec.id` with the `PRP` prefix stripped + `.` + `it.n` (so PRP1 item 2 → `1.2`); `StatusCircle`; item text; meta line (`it.codes` · `confidence {n}%` only when present and `result !== 'human'` · `deep-reviewed` if `reviewed` · `edited` if `edited`); chevron. Click → `pickItem(sec, it)` sets `picked` and `drawerOpen = true`; selected item gets `.selected`. Rendered only when `itemMatchesFilter` passes or filter is `all`.

**Collapse-default inversion (must-fix):** today an `openMap` entry that is not `=== false` is treated as *open*, and `expandAll` clears the map (→ all open). The redesign must initialize/flip this so PRP groups start **closed**, `Expand all` opens them, `Collapse` (default) closes them. Filtering to a non-`all` filter should still reveal matching items.

### Item drawer — retained verbatim (behavior)

Keep everything: header breadcrumb (`section.theme · section.id · Item n`), title + codes/confidence/badges, view-mode verdict row (`StatusCircle` size 32, label + sublabel, Override), AI Comment section, Reference-from-Policy card (or the context empty messages), "Re-review with Deep Analysis" (the staggered `DEEP_REVIEW_STEPS` thinking UI → `markReviewed`), edit mode (verdict dropdown, comment, ref section + quote), Save logic (`updateItemResult` with `ref` only when quote non-empty, `edited = true`), Override/Save disabled when `locked`, footer keyboard hints, and arrow-key item cycling synced to `picked`. **Add** `role="dialog"`, `aria-modal`, initial focus, focus trap, restore-focus-on-close, and background-scroll lock.

### Visual language (match the redesigned Library)

Reuse existing tokens/components — do not invent new ones:
- Color: `--primary*` scale, `--ok/--bad/--warn/--info` (+ `-bg` variants), ink scale; radii `--radius`/`-lg`/`-sm`; shadows `-sm`/`-md`/`-lg`.
- Type: `--sans` (Archivo / Vazirmatn bilingual), `--mono` (JetBrainsMono), `tabular-nums` for the score.
- Patterns: `.pl-brand-line`, `.pl-hero`/`.pl-eyebrow`/`.pl-hero-stats` spacing for the band; `.pl-chip`/`.chip` for filters.
- Components reused as-is: `VerdictBadge`, `StatusCircle`, `Chip`, `Icon`, `minibadge`.
- Keep `@scope (.pr-root)` isolation for all new styles.

### Responsive & accessibility (fixing audited gaps)

- Drop the fixed 340px rail; band full-width on top + checklist below already fixes the worst narrow-screen failure. Add real breakpoints: stack band clusters under ~1024px; single-column theme grid and stacked strengths/gaps under ~768px; never force horizontal scroll. Drawer goes near full-width under ~640px.
- `aria-expanded` + `aria-controls` on every PRP disclosure button; `aria-pressed` on the four filter chips; accessible labels on Expand all / Collapse; `aria-current` on active nav.
- Text labels (or `aria-label`/visually-hidden) for color-only `StatusCircle`, minibadge dots, and the `VerdictBadge` pulse: Compliant / Non-compliant / Needs human / Pending.
- Fix contrast: bump `--ink-400` (#8794A0) micro-text at 11–13px (item-num, item meta, theme-code, chip count, gap ref) to `--ink-500` (~6:1) or increase size.
- Visible `:focus-visible` rings on `.chip`, item rows, PRP headers, theme/band buttons (reuse `outline: 2px primary-100` + `box-shadow: 3px primary-50`).
- Touch targets ≥ ~44px on item rows, PRP headers, filter chips, band buttons.
- RTL/Arabic: set `direction` handling on `.pr-root` (today it relies on the parent); verify band flex clusters, chevron `scaleX(-1)`, score bars, drawer breadcrumb mirror; extend the existing `:dir(rtl)` block. Honor `prefers-reduced-motion` for new band/disclosure transitions.

## Files affected

- `views/ReviewView.svelte` — rewritten: band on top, three-tier collapsible checklist below, state-adaptive action zone; absorbs `ApprovalBanner` content.
- `styles.css` — replace `.review` / `.review-side` / `.side-card` rules with band + checklist styles; add breakpoints, focus rings, RTL/contrast fixes. Keep `@scope (.pr-root)`.
- `views/ItemDrawer.svelte` — add dialog semantics, focus trap, scroll lock (behavior otherwise unchanged).
- `views/ApprovalBanner.svelte` — content folded into the band; component removed or reduced once the band covers pending/approved/rejected status + Approve/Reject + reject-note form + error handling.
- Possibly small `aria-*` additions where status dots / badges are rendered (`StatusCircle.svelte`, `VerdictBadge.svelte`) if labels are added at the component level.

## Decisions (settled)

- Approved state shows the **recorded** decision (who/when) as the headline, not a live-recomputed verdict.
- Filters stay with the checklist, not promoted into the band.
- Clicking a critical gap opens the drawer **and** auto-expands its PRP group; read-only when locked.

## Risks & gotchas

- **Collapse-default inversion** — easy to get wrong; PRP groups must start closed without silently re-expanding on re-render. Initialize `openMap` deterministically.
- **Verdict vs status duality** — the band headline source differs by state; do not show a computed `approved` when the review is still `draft`/`pending`, and do not recompute over an `approved` record.
- **Hard-coded 85% → `verdictBands`** — re-sourcing changes displayed copy for any non-default checklist version; verify it reads through.
- **Rejection note** — `approval.note` is the only place the rejection reason appears; the band must preserve it for `rejected` reviews.
- **`POLICY_REVIEW_AUTOFILL`** — a backend/testing toggle (no frontend flag) that auto-marks items compliant; the progress framing must read from actual results, not assume reviewers manually clear items.
- **Admin role precedence** on a `pending` review → decision mode.
- **RTL** is only partially implemented today; a wider band increases mirroring risk — test explicitly.

## Open questions (non-blocking; sensible defaults chosen)

- Conditional verdict is label-only today (no CAP workflow exists) — leave as label.
- No frontend indicator for auto-filled vs human-reviewed items — not adding one now.
- Replace-document stays in the identity row (demoted visually, not removed).

## Verification

- Visual/manual smoke in the running app across all five (state, role) combinations in the matrix, using the Docker runtime per the project's Windows run notes.
- Confirm: collapsed-by-default; Expand all / Collapse; filters reveal/hide correctly; clicking an item opens the drawer and arrow-key cycling still works; clicking a critical gap expands + opens; Submit gating; Approve/Reject (note required); threshold reflects `verdictBands`; nothing from the old rail or approval banner is lost.
- Accessibility pass: keyboard-only disclosure + drawer, focus rings visible, `aria-expanded`/`aria-pressed` reflect state, contrast on micro-text.
- Responsive pass at ~1280 / ~1024 / ~768 / ~480px; RTL pass with an Arabic locale.
- No CSS leak outside `.pr-root` (the `@scope` guarantee holds).
