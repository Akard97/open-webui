# Effort switcher — Claude Code-style chip + popover slider

**Date:** 2026-07-17
**Status:** Approved (Variant B — Osool teal/gold)
**Mockup:** `docs/mockups/effort-switcher-v1.html` (Variant B)

## Overview

The per-user Effort control for Osool AI currently lives in Chat Controls →
Valves → Osool AI as a plain select dropdown (pipe `UserValves`, spec
2026-07-16 in the Osool-AI repo). This redesign surfaces it as a first-class
composer control modeled on Claude Code's effort switcher: a chip in the
message-input toolbar that opens a popover with a Faster↔Smarter slider.

Frontend-only. The pipe (v0.2.4), backend, and valve schema are untouched —
the new UI reads and writes the same per-user `EFFORT` valve through the
existing valves API.

## Decisions (locked with user)

- **Scope:** per-user (existing valve), persists across chats.
- **Levels:** 3 stops — `default` / `xhigh` / `max` — matching the pipe's
  `UserValves` Literal exactly. No `low`/`medium`.
- **Placement:** composer toolbar left cluster, after the IntegrationsMenu
  button (same row as `+`), before the generic Knobs valves button.
- **Approach:** new dedicated component wired to the valves API (Approach A).
- **Visual:** Variant B — Osool palette. X-High tints teal `#3d94a8`, Max
  tints gold `#e0a13f`, Default is muted gray. "Higher = warmer."

## Component

`src/lib/components/chat/MessageInput/EffortMenu.svelte`

### Anatomy

- **Chip** (toolbar button, pill): bolt icon + label.
  - `default`: muted gray, label "Effort".
  - `xhigh`: teal tint (text/bg/border), label "X-High".
  - `max`: gold tint, label "Max".
- **Popover** (opens above the chip):
  - Header: "Effort" + current level name (level name colored teal/gold),
    plus a "?" tooltip explaining what effort does.
  - Ends row: "Faster" (left) / "Smarter" (right).
  - Dotted track: canvas-drawn dot grid; dots up to the current stop grow and
    brighten in the accent color (teal for X-High, gold for Max), rest stay
    faint. White thumb, animated between 3 stop positions.
  - Stop labels under the track: Default · X-High · Max (active one
    highlighted).
  - Interaction: click anywhere on track jumps to nearest stop; drag snaps
    across stops; ArrowLeft/ArrowRight move one stop (a11y,
    `role="slider"`, `aria-valuenow`/`aria-valuetext`).
- Popover uses the same dropdown primitive as the neighboring menus
  (InputMenu's Dropdown) for consistent open/close, outside-click, and focus
  behavior. Composer row is already `dir="ltr"`; Faster/Smarter orientation
  stays LTR in RTL locales. Labels go through `$i18n.t` (add `ar` strings).

## Visibility / detection

Chip renders when ALL hold:

1. Exactly one model selected (same condition as the existing Knobs button,
   `MessageInput.svelte` ~line 1711).
2. Model `has_user_valves`.
3. The function's user-valves spec (`getUserValvesSpecById`, function id =
   `selectedModelIds[0].split('.')[0]`) has an `EFFORT` property whose
   enum/Literal values ⊇ {default, xhigh, max}.

Generic on purpose: any pipe exposing an `EFFORT` valve gets the chip — no
hardcoded Osool AI id. Spec fetch happens on selected-model change, cached
per function id for the session. Spec fetch failure → no chip (silent,
console-warn only). The generic Knobs valves button stays as-is (other
valves remain reachable).

## Data flow

- **Read:** on chip mount (per model change), `getUserValvesById` → current
  `EFFORT` → chip state. Missing/invalid value → treat as `default`.
- **Write:** on stop change, optimistic UI update, then
  `updateUserValvesById` with the **merged** valves object (spread current
  user valves, override `EFFORT`) so other valve fields are never clobbered.
  Rapid changes debounced (~400 ms, trailing).
- **Failure:** toast error, revert chip/slider to last confirmed value.
- No cross-tab sync (valve is server-side per-user; next chat/tab reads
  fresh).

## Error handling

- Valves GET fails → chip shows but stays at Default; first write re-syncs.
- Valves POST fails → toast + revert (above).
- Model switched while popover open → popover closes, state re-fetches.

## Testing

- Vitest: level↔valve mapping (default/xhigh/max, unknown → default); merge
  logic preserves unrelated valve keys; detection predicate (spec with/without
  EFFORT, multi-model → hidden).
- Manual browser smoke (light + dark): chip states, slider drag/click/keys,
  persistence across reload, valve visible in old Valves modal stays in sync,
  Arabic locale (RTL) layout.

## Out of scope

- Pipe/backend changes, new effort levels, per-chat effort.
- Removing the EFFORT field from the generic Valves modal.
- Thinking-block UI (separate feature, Osool-AI repo).
