# WorkOS P2b — shadcn Adoption Sweeps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace WorkOS's hand-rolled buttons, inputs, checkboxes, dropdown menus, and the create-flow modal host with the already-installed shadcn-svelte primitives, with near-zero visual change.

**Architecture:** Pure adoption sweep — no new primitives, no new files. Six tasks, each a self-contained set of component files, each committed and reviewed independently. shadcn components live at `$lib/components/ui/*` (nova style, tokens scoped to `.workos-root`); 11 component types are already consumed by 20+ WorkOS files, so every pattern in this plan has an in-repo precedent.

**Tech Stack:** Svelte 4 syntax in workos files (`on:click` NOT `onclick` in some files — MATCH WHATEVER THE FILE ALREADY USES), shadcn-svelte (bits-ui), Tailwind, vitest, svelte-check.

## Global Constraints

- Branch `osool`, commit directly (project precedent — user's Vite hot-reload watches this tree; no worktree).
- **Svelte file edits via the Edit tool ONLY** — shell writes corrupt files on this Windows box (cp1252).
- `git add` explicit paths only; never `git add -A`. NO prettier.
- Implementer/reviewer subagents: sonnet minimum. NEVER haiku on Svelte files.
- Verification per task: `npx vitest run src/lib/components/workos/lib` (all 194 must pass — these sweeps touch no lib logic, any test change is a red flag) + `npm run check` with **zero NEW workos-attributable errors** (baseline is noisy; grep output for the files you touched).
- **Do not start a Vite dev server. Ever.** Browser smoke is the user's manual pass.
- Visual parity is the spec: this wave was sold as "mostly invisible." Small deltas inherent to shadcn Button (h-8/h-7 heights, `rounded-lg`, focus rings) are ACCEPTED and listed in the smoke checklist; anything beyond that (color shifts, layout jumps, size changes >2px) is out of contract.
- Radius contract (design spec §3.3): controls `rounded-lg`, chips/pills `rounded-full`, cards `rounded-xl`, dialogs `rounded-2xl`. shadcn Button/Input/Dialog already comply.
- D5 tab decision: underline tabs (Topbar, AdminApp) and pill segments (Calendar Month/Week, Timeline zoom, My Work Assigned/Created) are **codified paradigms — do NOT convert them to shadcn Button/Tabs in this wave.**
- Clickable surfaces (task cards, list rows, calendar cells, notification rows, nav-tree rows, sidebar/drawer nav items) are **NOT buttons to migrate** — they keep their raw `<button>` wrappers and bespoke styling.
- `<textarea>` elements are out of scope (no shadcn Textarea installed; not in the spec's sweep list).
- Deliberately borderless/inline inputs stay hand-rolled where a shadcn Input's border/background would visibly change the design (explicitly: `views/calendar/DayCell.svelte` in-cell quick-add input — leave it).

## Import + variant contract (all tasks)

```svelte
import { Button, buttonVariants } from '$lib/components/ui/button';
import { Input } from '$lib/components/ui/input';
import { Checkbox } from '$lib/components/ui/checkbox';
import * as Dialog from '$lib/components/ui/dialog';
import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
import * as Select from '$lib/components/ui/select';
```

Variant/size mapping (binding for every swap):

| Hand-rolled role | shadcn |
|---|---|
| Primary/submit (solid brand bg) | `<Button size="sm">` (variant default = `bg-primary`) |
| Secondary/cancel (bordered neutral) | `<Button variant="outline" size="sm">` |
| Toolbar/utility text button (borderless, hover bg) | `<Button variant="ghost" size="sm">` |
| Destructive (delete team/workspace/comment) | `<Button variant="destructive" size="sm">` |
| Icon-only control | `<Button variant="ghost" size="icon-sm">` (or `icon-xs` where the current hit target is ≤24px) |
| Text/checkbox field | `<Input class="h-8" …>` (add height class only if the slot is tighter than default h-9… nova Input default; match current field height) |
| Boolean toggle | `<Checkbox checked={...} onCheckedChange={...}>` |

Rules that always apply: keep the file's existing event-handler syntax; preserve every `aria-*`, `title`, `data-*` attribute and handler on the swapped element; icon components keep their current size classes unless inside Button (Button sizes its own svg); `class` prop on shadcn components is for LAYOUT (margins, width, grid placement) only — never override colors/typography; Svelte 4 files pass content as children between the tags exactly as before.

---

### Task 1: FilterBar → DropdownMenu.CheckboxItem + Input + Button

**Files:**
- Modify: `src/lib/components/workos/chrome/FilterBar.svelte` (123 lines — full rewrite of markup, zero logic change)

**Interfaces:**
- Consumes: `boardFilter`-shaped `filter` prop (Writable<TaskFilter>), `flip(field, val)` helper, option lists — ALL UNCHANGED.
- Produces: same component API (props `filter`, `showAssignee`, slot). Consumers (BoardView:140, ListView:86, CalendarView:137, TimelineView:170) must not need edits.

- [ ] **Step 1: Replace the four facet menus.** Current anatomy per facet (status 49–61, priority 63–74, label 77–88, assignee 92–104): trigger `<button class="filter-chip">` + absolute `<div class="filter-menu">` + `<label class="filter-item"><input type="checkbox"></label>` rows + shared `open: string | null` state + `onWindowClick` dismiss. Replace each facet with:

```svelte
<DropdownMenu.Root>
	<DropdownMenu.Trigger>
		{#snippet child({ props })}
			<Button {...props} variant="outline" size="sm">
				Status{$filter.statuses.length ? ` · ${$filter.statuses.length}` : ''}
				<ChevronDown data-icon="inline-end" />
			</Button>
		{/snippet}
	</DropdownMenu.Trigger>
	<DropdownMenu.Content align="start" class="min-w-[11rem]">
		<DropdownMenu.Group>
			{#each STATUS_OPTIONS as s}
				<DropdownMenu.CheckboxItem
					checked={$filter.statuses.includes(s)}
					closeOnSelect={false}
					onCheckedChange={() => flip('statuses', s)}
				>
					{STATUS_LABEL[s]}
				</DropdownMenu.CheckboxItem>
			{/each}
		</DropdownMenu.Group>
	</DropdownMenu.Content>
</DropdownMenu.Root>
```

(Adapt names per facet: `priorities`/`labelIds`/`assigneeIds`, existing option sources and label lookups from the current file. Keep the count-suffix trigger text pattern the file already renders, whatever it is — read the current trigger content and preserve it. Keep the existing chevron icon component the file uses; if it's the local `Icon.svelte`, keep that, sized as today.) **Precedent for `{#snippet child({ props })}` triggers + CheckboxItem-style menus: `views/detail/AssigneeField.svelte:24-52`. Read it first and follow its conventions.** If `closeOnSelect` is not a supported prop in this bits-ui version (check AssigneeField or dropdown-menu-checkbox-item.svelte), the equivalent is `onSelect={(e) => e.preventDefault()}` on the item — verify against the installed component source, pick what it supports.

- [ ] **Step 2: Delete the dead machinery.** Remove `open` state, `toggle(k)`, `onWindowClick`, `<svelte:window onclick=…>` (lines 10–19, 32), and the `.filter-chip` / `.filter-menu` / `.filter-item` style block (lines 115–123). Nothing else may still reference them (grep the file).

- [ ] **Step 3: Search input → shadcn Input.** Lines 36–44: keep the wrapper + magnifier icon positioning; swap the raw `<input>` for `<Input class="h-8 pl-8 …layout-only classes…" placeholder="Search title or key…" bind:value={$filter.text} />` preserving the exact placeholder + binding. Match current width classes.

- [ ] **Step 4: Verify + commit.**

Run: `npx vitest run src/lib/components/workos/lib` → 194 passed. `npm run check` → no errors mentioning FilterBar.svelte.
Grep: `rg "filter-menu|onWindowClick|type=\"checkbox\"" src/lib/components/workos/chrome/FilterBar.svelte` → no hits.

```bash
git add src/lib/components/workos/chrome/FilterBar.svelte
git commit -m "refactor(workos): FilterBar facets on shadcn DropdownMenu.CheckboxItem"
```

---

### Task 2: ModalHost → shadcn Dialog (+ Input/Select/Button inside)

**Files:**
- Modify: `src/lib/components/workos/views/ModalHost.svelte` (87 lines)

**Interfaces:**
- Consumes: `openModal` store (`lib/store.ts:22-28`, `ModalRequest` union). Handles ONLY kinds `'team' | 'workspace' | 'workstream'` (settings kinds are separate components — untouched).
- Produces: same store contract. `close()` still `openModal.set(null)`. Submit flow (`submit()` → API → `loadBootstrap()` → close) byte-identical.

- [ ] **Step 1: Swap shell.** Replace the hand-rolled `fixed inset-0 z-50` overlay + backdrop div (lines 59–60) with the pattern the settings dialogs already use — read `chrome/access/TeamSettingsDialog.svelte:157` first:

```svelte
<Dialog.Root open={req != null} onOpenChange={(o) => { if (!o) close(); }}>
	<Dialog.Content class="sm:max-w-md">
		<Dialog.Header>
			<Dialog.Title>{title}</Dialog.Title>
		</Dialog.Header>
		… form fields …
		<Dialog.Footer>
			<Button variant="outline" size="sm" onclick={close}>Cancel</Button>
			<Button size="sm" onclick={submit} disabled={busy || !name.trim()}>Create</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
```

Keep the existing reactive `req` derivation, `title` text, `busy`/validation logic exactly as-is (whatever the current file names them — preserve names). Preserve the exact button labels and disabled conditions currently in lines 82–83. The manual close button (line 64) is replaced by Dialog's built-in close. This upgrade adds Escape + focus trap — intended.

- [ ] **Step 2: Fields.** Name/key inputs (lines 70–72) → `<Input>`; visibility select (lines 75–78) → shadcn `Select` following the exact pattern in `WorkspaceSettingsDialog.svelte` (read its Select usage; same option values/labels as current markup). Keep labels, `bind:value` targets, placeholder text identical.

- [ ] **Step 3: Verify + commit.**

Run: `npx vitest run src/lib/components/workos/lib` → 194 passed. `npm run check` → nothing new for ModalHost.svelte.
Grep: `rg "bg-black/40|inset-0" src/lib/components/workos/views/ModalHost.svelte` → no hits.

```bash
git add src/lib/components/workos/views/ModalHost.svelte
git commit -m "refactor(workos): create-flow modals on shadcn Dialog"
```

---

### Task 3: TeamSwitcher team-list dropdown → DropdownMenu

**Files:**
- Modify: `src/lib/components/workos/chrome/TeamSwitcher.svelte` (92 lines)

**Interfaces:**
- Consumes: teams list, `currentTeamId` store, `openModal.set(...)` calls (lines 62, 80, 86) — unchanged.
- Produces: same rendered trigger row inside the sidebar; ContextMenu (right-click "Team settings…", lines 41–67) stays exactly as-is, wrapping the new DropdownMenu trigger.

- [ ] **Step 1: Replace the hand-rolled menu.** Lines 68–91 (`{#if teamMenuOpen}` absolute panel) + `teamMenuOpen` state (11) + `onWindowClick` (16–18, 37) + Escape keydown handler → one `DropdownMenu.Root`. The existing trigger button (line 45, `onclick` toggle) becomes the `DropdownMenu.Trigger` via `{#snippet child({ props })}` spread onto the SAME button markup (keep its current bespoke classes — it's a sidebar affordance, not a standard control; do NOT convert it to shadcn Button). Menu content:

```svelte
<DropdownMenu.Content align="start">
	<DropdownMenu.Group>
		{#each teams as t}
			<DropdownMenu.Item onSelect={() => selectTeam(t.id)}>
				<span class="truncate">{t.name}</span>
				{#if t.id === $currentTeamId}<CheckIcon-as-currently-rendered />{/if}
			</DropdownMenu.Item>
		{/each}
	</DropdownMenu.Group>
	<DropdownMenu.Separator />
	<DropdownMenu.Group>
		{#if canManage}<DropdownMenu.Item onSelect={() => openModal.set({ kind: 'team-settings', teamId: $currentTeamId })}>Team settings…</DropdownMenu.Item>{/if}
		<DropdownMenu.Item onSelect={() => openModal.set({ kind: 'team' })}>New team</DropdownMenu.Item>
	</DropdownMenu.Group>
</DropdownMenu.Content>
```

Use the EXACT current handler bodies/guards from lines 70–89 (team select behavior, `canManage` gating of "Team settings…", exact `openModal.set` payloads including teamId fields as currently written — read the file, copy them verbatim). Keep the current checkmark rendering. Width: match the current panel (`left-[0.4375rem] right-[0.4375rem]` inset look) via the anchor-width var or an explicit min-width — visually equivalent is the bar.

- [ ] **Step 2: Confirm ContextMenu coexistence.** Right-click settings path (ContextMenu.Trigger wrapping, line 42–45) must still work with DropdownMenu on left-click. If nesting triggers on one element fights bits-ui, put DropdownMenu.Trigger innermost. Report in the task report which structure you landed.

- [ ] **Step 3: Verify + commit.**

Run: `npx vitest run src/lib/components/workos/lib` → 194 passed. `npm run check` → nothing new for TeamSwitcher.svelte.
Grep: `rg "teamMenuOpen|onWindowClick" src/lib/components/workos/chrome/TeamSwitcher.svelte` → no hits.

```bash
git add src/lib/components/workos/chrome/TeamSwitcher.svelte
git commit -m "refactor(workos): TeamSwitcher team list on shadcn DropdownMenu"
```

---

### Task 4: Detail-drawer sweep — CommentComposer, CommentItem, SubtasksPanel, DueDateCell

**Files:**
- Modify: `src/lib/components/workos/views/detail/CommentComposer.svelte` (buttons: mention 40, attach 41, comment/submit 44; file input 42 stays; textarea stays)
- Modify: `src/lib/components/workos/views/detail/CommentItem.svelte` (buttons: edit 28, delete 31, save 37, cancel 38; edit textarea stays)
- Modify: `src/lib/components/workos/views/detail/SubtasksPanel.svelte` (checkbox 21–27 → `Checkbox`; delete 31, add 54 → Buttons)
- ~~Modify: DueDateCell trigger → Button ghost~~ **AMENDED during execution (2026-07-10): DueDateCell lives at `views/cells/DueDateCell.svelte` and its trigger STAYS hand-rolled** — the cell-trigger family (StatusCell/PriorityCell/DueDateCell) shares byte-identical ~24px trigger anatomy in the same ListView grid row; converting one produced an out-of-contract row-height/alignment jump (Task 4 review). The `type=date` input also stays raw.

**Interfaces:**
- Consumes: `$lib/components/ui/button|checkbox` (Task-independent; DetailHeader in the same folder already imports Button — read it for local conventions).
- Produces: no API changes; all component props/events unchanged.

- [ ] **Step 1: Buttons.** Apply the variant table: submit "Comment" = default; mention/attach = ghost icon-sm; edit/delete on comments = ghost icon-xs or ghost sm matching current hit target (delete comment = `variant="ghost"` with its current red text class kept as layout? NO — destructive text means `variant="destructive"`); save = default sm; cancel = ghost sm; subtask delete = ghost icon-xs; add subtask = ghost sm. (DueDateCell trigger: amended — stays hand-rolled, see Files list.) Preserve all handlers/aria/title attributes.
- [ ] **Step 2: SubtasksPanel checkbox.** `<input type="checkbox" checked={…} onchange={…}>` → `<Checkbox checked={…} onCheckedChange={…} class="size-4" aria-label={…as current…}/>`. Toggle handler body unchanged. If the row's click target wraps the checkbox, keep the wrapping semantics (no double-toggle — verify the handler doesn't fire twice).
- [ ] **Step 3: Verify + commit.**

Run: `npx vitest run src/lib/components/workos/lib` → 194 passed. `npm run check` → nothing new for the 4 files.

```bash
git add src/lib/components/workos/views/detail/CommentComposer.svelte src/lib/components/workos/views/detail/CommentItem.svelte src/lib/components/workos/views/detail/SubtasksPanel.svelte
git commit -m "refactor(workos): detail drawer controls on shadcn Button/Checkbox"
```

---

### Task 5: View-toolbar sweep — Board, List, Calendar, Timeline, AttentionList

**Files:**
- Modify: `src/lib/components/workos/views/BoardView.svelte` (Add New 145, Add task 160 → Buttons; quick-add title inputs 143, 182 → Input IF currently bordered fields — if borderless inline, leave and note in report)
- Modify: `src/lib/components/workos/views/ListView.svelte` (Add new 112, Add task 245 → Buttons; collapse 125 + title click 153 are row affordances — LEAVE; quick-add inputs 104–110, 237–243 same bordered-only rule)
- Modify: `src/lib/components/workos/views/CalendarView.svelte` (period nav + Today 142–146 → Buttons ghost/outline; **Month/Week toggle 149–150 = D5 pill segment — LEAVE**; unscheduled toggle 161–167 — LEAVE, bespoke rail affordance)
- Modify: `src/lib/components/workos/views/TimelineView.svelte` (Today 184, Add new 198 → Buttons; **zoom buttons 174–179 = D5 pill segment — LEAVE**; quick-add input 189–196 bordered-only rule)
- Modify: `src/lib/components/workos/views/overview/AttentionList.svelte` (show all/fewer 45 → Button ghost xs/sm)

**Interfaces:** none new; ListView + TaskCard already import Button — follow their conventions.

- [ ] **Step 1: Buttons per the variant table.** "Add task"/"Add new" = ghost sm (they're quiet affordances today — match current visual weight; if one is solid brand today, default variant). Period nav arrows = ghost icon-sm. Today = outline sm.
- [ ] **Step 2: Quick-add inputs.** Bordered-only rule: swap to `<Input class="h-8">` (or h-7 to match slot) ONLY if the current input renders a visible bordered field; report each leave-decision.
- [ ] **Step 3: Verify + commit.**

Run: `npx vitest run src/lib/components/workos/lib` → 194 passed. `npm run check` → nothing new for the 5 files.

```bash
git add src/lib/components/workos/views/BoardView.svelte src/lib/components/workos/views/ListView.svelte src/lib/components/workos/views/CalendarView.svelte src/lib/components/workos/views/TimelineView.svelte src/lib/components/workos/views/overview/AttentionList.svelte
git commit -m "refactor(workos): view toolbars on shadcn Button/Input"
```

---

### Task 6: Admin + chrome + dialog-footer sweep

**Files:**
- Modify: `src/lib/components/workos/views/admin/RulesTab.svelte` (save 81 → Button default sm; selects 38–48 → shadcn Select per WorkspaceSettingsDialog pattern; checkboxes 59–68 → Checkbox; number input 72–78 → `<Input type="number">`)
- Modify: `src/lib/components/workos/views/admin/AdminApp.svelte` (back 22 → Button ghost sm; **tab buttons 26 = D5 underline tabs — LEAVE**)
- Modify: `src/lib/components/workos/chrome/Topbar.svelte` (disabled trio rename/share/automation 32, 44–45 → `<Button variant="ghost" size="sm" disabled>` — Button's disabled opacity replaces the hand-rolled 50%-opacity treatment from Phase 1; **workstream tab selector 54 = D5 underline tabs — LEAVE**)
- Modify: `src/lib/components/workos/chrome/MobileHeader.svelte` (nav toggle 18 → Button ghost icon-sm)
- Modify: `src/lib/components/workos/chrome/access/TeamSettingsDialog.svelte` (footer cancel/delete 325–326 → Button outline / destructive, both sm)
- Modify: `src/lib/components/workos/chrome/access/WorkspaceSettingsDialog.svelte` (footer cancel/delete 329–330 → same)
- Modify: `src/lib/components/workos/chrome/access/RestrictConfirmDialog.svelte` (cancel/restrict 22–28 → Button outline / destructive sm)
- **LEAVE:** Sidebar.svelte nav buttons + rail toggle (bespoke nav), NavDrawer.svelte (mobile shell, separate domain), WorkstreamTree.svelte row/kebab buttons (nav tree).

**Interfaces:** none new. The three access dialogs do NOT currently import Button (census: Button imports exist only in DetailHeader/ListView/TaskCard) — add `import { Button } from '$lib/components/ui/button';` to each.

- [ ] **Step 1: Sweep per the variant table.** Destructive actions ("Delete team", "Delete workspace", "Restrict") = `variant="destructive"`; their busy/disabled conditions preserved verbatim. RulesTab keeps its loading state + sonner toasts (Phase 1 work) untouched.
- [ ] **Step 2: Verify + commit.**

Run: `npx vitest run src/lib/components/workos/lib` → 194 passed. `npm run check` → nothing new for the 7 files.

```bash
git add src/lib/components/workos/views/admin/RulesTab.svelte src/lib/components/workos/views/admin/AdminApp.svelte src/lib/components/workos/chrome/Topbar.svelte src/lib/components/workos/chrome/MobileHeader.svelte src/lib/components/workos/chrome/access/TeamSettingsDialog.svelte src/lib/components/workos/chrome/access/WorkspaceSettingsDialog.svelte src/lib/components/workos/chrome/access/RestrictConfirmDialog.svelte
git commit -m "refactor(workos): admin, chrome and dialog footers on shadcn controls"
```

---

## Final verification (whole wave)

- `npx vitest run src/lib/components/workos/lib` → 194/194.
- `npm run check` → zero new workos errors vs pre-wave baseline.
- Greps: `rg "filter-menu|teamMenuOpen" src/lib/components/workos` → 0; `rg "onWindowClick" src/lib/components/workos` → 0.
- Focus-visible dividend: every swapped control now carries shadcn's built-in `focus-visible` ring — first real dent in the spec §3.3 focus contract.

## Browser smoke additions (user's manual pass — CONSOLIDATED post-wave, includes review findings)

- FilterBar: facet menus now shadcn (keyboard nav + Escape work; close on outside click as before); trigger chips now `rounded-lg` outline buttons (~2px shorter, 0.8rem text); search field shadcn-styled.
- Create team/workspace/workstream: rounded-2xl shadcn Dialog, Escape closes, focus trapped; NEW tinted/bordered Dialog.Footer band behind Cancel/Create; check Name field still autofocuses (focus-trap may grab first); check console for a missing-Dialog.Description a11y warning.
- TeamSwitcher: team list = shadcn menu (arrow keys work); right-click "Team settings…" still works; menu width matches trigger.
- **DESTRUCTIVE BUTTONS — DECISION PENDING:** Delete team / Delete workspace / Restrict are now nova soft red-tint pills (`bg-destructive/10 text-destructive`), NOT the old solid red `bg-red-600 text-white`. Same treatment on comment-delete (hover-reveal red pill, was gray-then-red icon). Confirm taste or request solid-red variant amendment.
- Buttons everywhere swept: heights normalize to h-7/h-8, radius rounded-lg, focus rings on keyboard focus. Month/Week + zoom pills, Topbar/Admin underline tabs, sidebar/tree/nav rows, StatusCell/PriorityCell/DueDateCell triggers: UNCHANGED (any change = bug).
- Topbar disabled trio (Rename/Share/Automation): Share/Automation lose their at-rest border pill (ghost variant) — check they don't read invisible; tooltips no longer show (pointer-events-none on disabled).
- Board columns: per-column add-task plus glyph now 12px inside a 24px button, next to the untouched 16px "More" stub — check optics.
- ListView: "Add task" per-status link gains ghost-button chrome (was bare text link); "Columns" trigger restyled to match facet buttons (dregs).
- Calendar/Timeline: "Today" ~2px shorter; toolbars otherwise governed by untouched pills.
- Subtask checkboxes: shadcn square w/ check animation (was native); "Add subtask" gains ghost chrome (was bare text link).
- RulesTab: shadcn selects/checkboxes/number input.
- Mobile (<768px): all shadcn Inputs render 16px text (was 14px) — intentional shadcn default, prevents iOS focus-zoom.
