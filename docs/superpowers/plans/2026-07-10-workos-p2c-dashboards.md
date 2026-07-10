# WorkOS P2c — Dashboard Primitives Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the Overview ink hero (locked decision D4), land the KpiNumeral + DeltaBadge + EmptyState primitives, and adopt them across Overview, My Work, Momentum, Calendar, Inbox, and Timeline.

**Architecture:** Three new presentation primitives in `src/lib/components/workos/ui/` (same pattern as StatusBadge/PriorityFlag: `export let` props, tokens from `lib/colors.ts` + `--wos-*` CSS vars). KpiBand is rewritten as a standard themed card — its 14 private hexes are deleted, not tokenized. Adoption sweeps then replace the three numeral styles, three delta treatments, and 13 bare empty states.

**Tech Stack:** Svelte 5 (legacy `export let` components), Tailwind v4 (`--color-*` theme vars available), shadcn-svelte Button, vitest (lib tests only — no component tests in this repo).

**Mockups approved 2026-07-10:** https://claude.ai/code/artifact/f8a9366c-4c5f-4973-9a2c-b361666cf7a1

**User decisions (2026-07-10):**
1. "New tasks" dot = **gray-500 neutral** (`var(--color-gray-500)`) — no new hue.
2. My Work numerals **34px → 28px** display step (spec-strict, weight stays 700, `font-mono` sub dropped).
3. EmptyState adopts **all 13 bare sites** this wave. Board columns keep their compact status-dot version.
4. Direction approved as mocked: band-as-card with hairline KPI columns (xl only), Calendar-style pill segment, DeltaBadge tint pills, Timeline-canon empty states.

## Global Constraints

- Branch `osool`, commit directly (project precedent). `git add` **explicit paths only** — working tree may hold unrelated files; never `git add -A`.
- **Svelte edits via Edit/Write tools only. Implementers must be sonnet-class — NEVER haiku (cp1252 write corruption on this Windows box).** No prettier runs.
- Radius contract: controls `rounded-lg` · chips/pills `rounded-full` · cards `rounded-xl` · overlays `rounded-2xl`. No bare `rounded`.
- Type ramp: KPI numerals use the `.wos-display` class (28px/700/tabular/-0.02em, already in styles.css). No new `text-[Npx]` sizes outside the existing ramp; 11px/12px/13px captions match surrounding file idiom.
- Colors: **never** hardcode `#00a5ba` for UI accent (use `bg-primary`/`text-primary`); data/outcome colors via `--wos-*` vars or `lib/colors.ts` exports. The banned hexes `#5DCAA5 #f0b47a #f27d72 #8fa3ff #101623 #1b2434 #232f45 #7e8aa0 #9aa6ba #aab5c8 #2a3651 #123c2c #3c1a1a` must have **zero** matches in `src/lib/components/workos` when this wave completes.
- Tests: `npx vitest run src/lib/components/workos` must stay green (194 tests, none removed). Typecheck: `npm run check` — compare against baseline noise; no NEW errors in workos files.
- Commit messages: conventional commits, `feat(workos):` / `refactor(workos):` style, normal prose.

## File Structure

- Create: `src/lib/components/workos/ui/DeltaBadge.svelte` — tinted delta pill (arrow + value).
- Create: `src/lib/components/workos/ui/KpiNumeral.svelte` — display-step numeral + optional DeltaBadge.
- Create: `src/lib/components/workos/ui/EmptyState.svelte` — block + quiet empty-state variants.
- Modify: `src/lib/components/workos/ui/Icon.svelte` — add `arrow-down` glyph.
- Modify: `src/lib/components/workos/views/overview/KpiBand.svelte` — full rewrite (ink → themed card).
- Modify: `src/lib/components/workos/views/MyWorkView.svelte` — stat tiles adopt KpiNumeral/DeltaBadge; main list + 4 rails adopt EmptyState.
- Modify: `src/lib/components/workos/views/overview/MomentumCard.svelte` — completion delta adopts DeltaBadge.
- Modify: `src/lib/components/workos/views/OverviewView.svelte`, `views/overview/PulseCard.svelte`, `views/overview/AttentionList.svelte`, `views/overview/TeamTable.svelte` — EmptyState adoption.
- Modify: `src/lib/components/workos/views/CalendarView.svelte`, `views/InboxView.svelte`, `views/TimelineView.svelte` — EmptyState adoption.
- NOT touched: `views/BoardView.svelte` empty state (kept by decision), `views/overview/DistributionCard.svelte` 16px counts (list counts, not KPIs — flagged and accepted), MomentumCard chart series colors `#c5e8ee`/`#00a5ba` (chart data colors, out of scope).

---

### Task 1: DeltaBadge + KpiNumeral primitives (+ arrow-down icon)

**Files:**
- Modify: `src/lib/components/workos/ui/Icon.svelte` (LUCIDE map, after the `'arrow-up'` entry at line 47)
- Create: `src/lib/components/workos/ui/DeltaBadge.svelte`
- Create: `src/lib/components/workos/ui/KpiNumeral.svelte`

**Interfaces:**
- Consumes: `tint(color)` from `../lib/colors` (signature `tint(color: string, pct = 14): string`); CSS vars `--wos-done` (#769a4a both modes) and `--wos-danger` (#dc2626 light / #f87171 dark) from styles.css; `.wos-display` ramp class.
- Produces:
  - `DeltaBadge` props: `up: boolean` (arrow direction), `text: string` (pre-formatted, e.g. `"vs 9"`, `"2"`, `"0.5"`), `positive: boolean | null = null` (color tone override; defaults to `up`). Used by Tasks 2–3.
  - `KpiNumeral` props: `value: string | number`, `delta: { up: boolean; text: string; positive?: boolean } | null = null`. Used by Tasks 2–3.

- [ ] **Step 1: Add `arrow-down` to Icon.svelte**

In the `LUCIDE` record, immediately after the `'arrow-up'` entry, add:

```ts
	'arrow-down': '<path d="M12 5v14"/><path d="m19 12-7 7-7-7"/>',
```

- [ ] **Step 2: Create DeltaBadge.svelte**

```svelte
<script lang="ts">
	// Canonical delta badge (spec §4): tinted pill + arrow + tabular value.
	// `up` is the arrow direction; `positive` overrides the color when goodness
	// doesn't track direction (completion time falling is good → down + green).
	import Icon from './Icon.svelte';
	import { tint } from '../lib/colors';

	export let up: boolean;
	export let text: string;
	export let positive: boolean | null = null;

	$: color = (positive ?? up) ? 'var(--wos-done)' : 'var(--wos-danger)';
</script>

<span
	class="inline-flex items-center gap-[3px] rounded-full py-0.5 pr-[7px] pl-[5px] text-[11px] leading-[1.35] font-medium tabular-nums"
	style="color:{color}; background:{tint(color)}"
>
	<Icon name={up ? 'arrow-up' : 'arrow-down'} size={10} strokeWidth={3} />
	{text}
</span>
```

- [ ] **Step 3: Create KpiNumeral.svelte**

```svelte
<script lang="ts">
	// Canonical KPI numeral: the .wos-display step (28px/700 tabular, styles.css)
	// with an optional DeltaBadge on the baseline. Absorbs the 16/22/34px trio.
	import DeltaBadge from './DeltaBadge.svelte';

	export let value: string | number;
	export let delta: { up: boolean; text: string; positive?: boolean } | null = null;
</script>

<span class="inline-flex items-baseline gap-1.5">
	<span class="wos-display text-gray-900 dark:text-gray-100">{value}</span>
	{#if delta}
		<DeltaBadge up={delta.up} text={delta.text} positive={delta.positive ?? null} />
	{/if}
</span>
```

- [ ] **Step 4: Verify**

Run: `npx vitest run src/lib/components/workos` → 194 passed, 0 failed.
Run: `npm run check` → no NEW errors mentioning `DeltaBadge`, `KpiNumeral`, or `Icon.svelte` (baseline noise in unrelated files is pre-existing and fine).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/ui/Icon.svelte src/lib/components/workos/ui/DeltaBadge.svelte src/lib/components/workos/ui/KpiNumeral.svelte
git commit -m "feat(workos): DeltaBadge + KpiNumeral primitives"
```

---

### Task 2: KpiBand ink retirement (D4)

**Files:**
- Modify: `src/lib/components/workos/views/overview/KpiBand.svelte` (full rewrite — replace the entire file)

**Interfaces:**
- Consumes: `KpiNumeral` from Task 1 (`value`, `delta`); `--wos-status-in-progress`, `--wos-due`, `--wos-danger`, `--wos-done`, `--color-gray-500` CSS vars; `.wos-heading` ramp class.
- Produces: nothing new — the component's own props (`kpis`, `weeks`, `onWeeks`, `workspaceName`, `workstreamName`, `taskCount`, `peopleCount`) are **unchanged**, so `OverviewView.svelte` needs no edit in this task.

- [ ] **Step 1: Replace KpiBand.svelte entirely with:**

```svelte
<script lang="ts">
	import type { OverviewKpis } from '../../lib/overview';
	import KpiNumeral from '../../ui/KpiNumeral.svelte';

	export let kpis: OverviewKpis;
	export let weeks: 4 | 6 | 12;
	export let onWeeks: (w: 4 | 6 | 12) => void;
	export let workspaceName = '';
	export let workstreamName = '';
	export let taskCount = 0;
	export let peopleCount = 0;

	const WEEK_OPTIONS: (4 | 6 | 12)[] = [4, 6, 12];

	// Dot hues are data colors from the token layer (D2/D3); "new tasks" is
	// deliberately neutral gray-500 (user decision 2026-07-10, no creation hue).
	type Tile = { dot: string; label: string; value: string; delta?: { up: boolean; text: string } | null; caption: string };
	$: tiles = [
		{ dot: 'var(--wos-status-in-progress)', label: 'Open tasks', value: String(kpis.open),
			caption: `${kpis.inProgress} in progress · ${kpis.inReview} in review` },
		{ dot: 'var(--wos-due)', label: 'Due this week', value: String(kpis.dueThisWeek),
			caption: kpis.dueTomorrow ? `${kpis.dueTomorrow} due tomorrow` : 'none tomorrow' },
		{ dot: 'var(--wos-danger)', label: 'Overdue', value: String(kpis.overdue),
			caption: kpis.oldestOverdueDays != null ? `oldest ${kpis.oldestOverdueDays}d late` : 'all clear' },
		{ dot: 'var(--wos-done)', label: 'Completed', value: String(kpis.completed7d),
			delta: kpis.completed7d === kpis.completedPrev7d ? null
				: { up: kpis.completed7d > kpis.completedPrev7d, text: `vs ${kpis.completedPrev7d}` },
			caption: 'last 7 days vs prior 7' },
		{ dot: 'var(--color-gray-500)', label: 'New tasks', value: String(kpis.new7d), caption: 'added in last 7 days' }
	] satisfies Tile[];
</script>

<section
	class="rounded-xl border border-gray-200 bg-white p-4 sm:p-5 dark:border-gray-800 dark:bg-gray-900"
	aria-label="Workstream key figures"
>
	<div class="mb-4 flex flex-wrap items-center gap-3">
		<div class="min-w-0">
			<div class="text-[11px] font-medium text-gray-400 dark:text-gray-500">{workspaceName ? `${workspaceName} / ` : ''}{workstreamName}</div>
			<h2 class="wos-heading mt-0.5 text-gray-900 dark:text-gray-100">Overview</h2>
		</div>
		<div class="ml-auto text-[11px] text-gray-400 dark:text-gray-500">{taskCount} tasks · {peopleCount} people</div>
		<div class="flex rounded-full bg-gray-100 p-0.5 dark:bg-gray-800" role="group" aria-label="Momentum window">
			{#each WEEK_OPTIONS as w (w)}
				<button
					type="button"
					class="rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors
						{weeks === w ? 'bg-primary text-primary-foreground shadow-sm' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'}"
					aria-pressed={weeks === w}
					onclick={() => onWeeks(w)}
				>{w}w</button>
			{/each}
		</div>
	</div>
	<div class="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-5 xl:gap-0 xl:divide-x xl:divide-gray-100 xl:dark:divide-gray-800">
		{#each tiles as t (t.label)}
			<div class="min-w-0 xl:px-4 xl:first:pl-0 xl:last:pr-0" aria-label="{t.label}: {t.value}">
				<div class="flex items-center gap-1.5 text-[11px] font-medium text-gray-500 dark:text-gray-400">
					<span class="h-2 w-2 flex-none rounded-full" style="background:{t.dot}"></span>{t.label}
				</div>
				<div class="mt-1.5"><KpiNumeral value={t.value} delta={t.delta ?? null} /></div>
				<div class="mt-1 text-[11px] text-gray-400 dark:text-gray-500">{t.caption}</div>
			</div>
		{/each}
	</div>
</section>
```

Design notes locked by the approved mockup: hairline column dividers appear only at `xl` (single 5-col row); below `xl` the grid wraps with plain gaps. The 4w/6w/12w toggle is the Calendar Month/Week pill segment recipe (`bg-gray-100 dark:bg-gray-800` track, active `bg-primary text-primary-foreground shadow-sm`) at 11px. The `--wos-danger` dot auto-flips to `#f87171` in dark mode via the token — do not hardcode either hex.

- [ ] **Step 2: Verify the ink hexes are dead**

Run: `rg '#101623|#1b2434|#232f45|#7e8aa0|#9aa6ba|#aab5c8|#2a3651|#123c2c|#3c1a1a|#8fa3ff|#f0b47a|#f27d72|#5DCAA5' src/lib/components/workos` → **no matches**.

- [ ] **Step 3: Verify**

Run: `npx vitest run src/lib/components/workos` → 194 passed.
Run: `npm run check` → no NEW errors mentioning `KpiBand`.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/views/overview/KpiBand.svelte
git commit -m "refactor(workos): retire Overview ink hero, KpiBand becomes themed card (D4)"
```

---

### Task 3: KpiNumeral/DeltaBadge adoption — My Work stat tiles + Momentum delta

**Files:**
- Modify: `src/lib/components/workos/views/MyWorkView.svelte` (stat-tile markup, currently lines ~193–210)
- Modify: `src/lib/components/workos/views/overview/MomentumCard.svelte` (completion delta, currently lines ~60–64)

**Interfaces:**
- Consumes: `KpiNumeral` + `DeltaBadge` from Task 1, exact props as defined there.
- Produces: nothing for later tasks.

- [ ] **Step 1: MyWorkView stat tiles**

In `MyWorkView.svelte`, add to the imports (next to the other `../ui/` imports):

```ts
	import KpiNumeral from '../ui/KpiNumeral.svelte';
```

Then replace this block inside the stat-tile `{#each stats4 as s (s.label)}` loop:

```svelte
					<div class="mt-3 flex items-baseline gap-1.5">
						<span class="text-[34px] font-bold tracking-tight leading-none tabular-nums text-gray-900 dark:text-gray-100">{s.value}</span>
						{#if s.delta != null && s.delta > 0}
							<span class="inline-flex items-center gap-px text-[13px] font-semibold text-emerald-600 dark:text-emerald-400">
								<Icon name="arrow-up" size={12} />{s.delta}
							</span>
						{/if}
					</div>
```

with:

```svelte
					<div class="mt-3">
						<KpiNumeral value={s.value} delta={s.delta != null && s.delta > 0 ? { up: true, text: String(s.delta) } : null} />
					</div>
```

And replace the mono sub-label line (spec §3.2 drops `font-mono` sub-labels):

```svelte
					<div class="mt-1 text-[12px] font-mono text-gray-400 dark:text-gray-500">{s.sub}</div>
```

with:

```svelte
					<div class="mt-1 text-[12px] text-gray-400 dark:text-gray-500">{s.sub}</div>
```

Behavior preserved on purpose: deltas render only when `> 0` (same guard as today), so this stays an up-only badge here.

- [ ] **Step 2: MomentumCard completion delta**

In `MomentumCard.svelte`, add the import:

```ts
	import DeltaBadge from '../../ui/DeltaBadge.svelte';
```

Then replace:

```svelte
				{#if delta}
					<span class={delta.faster ? 'text-green-700 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
						{delta.faster ? '▾' : '▴'}{delta.text}
					</span>
				{/if}
```

with:

```svelte
				{#if delta}
					<DeltaBadge up={!delta.faster} positive={delta.faster} text={delta.text} />
				{/if}
```

Semantics note (why `positive` ≠ `up` here): average completion time falling is *good* — the arrow must point down while the badge stays green. This is exactly the `positive` override case. Do NOT "simplify" to `up={delta.faster}`.

- [ ] **Step 3: Verify**

Run: `npx vitest run src/lib/components/workos` → 194 passed.
Run: `npm run check` → no NEW errors mentioning `MyWorkView` or `MomentumCard`.
Run: `rg 'text-\[34px\]|font-mono' src/lib/components/workos/views/MyWorkView.svelte` → no matches.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/views/MyWorkView.svelte src/lib/components/workos/views/overview/MomentumCard.svelte
git commit -m "refactor(workos): My Work tiles and Momentum delta adopt KpiNumeral/DeltaBadge"
```

---

### Task 4: EmptyState primitive + dashboard adopters (Overview + My Work)

**Files:**
- Create: `src/lib/components/workos/ui/EmptyState.svelte`
- Modify: `src/lib/components/workos/views/OverviewView.svelte` (lines ~45–49)
- Modify: `src/lib/components/workos/views/overview/PulseCard.svelte` (line ~26)
- Modify: `src/lib/components/workos/views/overview/AttentionList.svelte` (line ~28)
- Modify: `src/lib/components/workos/views/overview/TeamTable.svelte` (line ~24)
- Modify: `src/lib/components/workos/views/MyWorkView.svelte` (main-list empty ~286; rails ~361, ~369, ~391, ~417)

**Interfaces:**
- Consumes: `Icon` (existing), shadcn `Button` from `$lib/components/ui/button`.
- Produces: `EmptyState` props: `title: string`, `variant: 'block' | 'quiet' = 'block'`, `icon = ''` (Icon name), `sub = ''`, `ctaLabel = ''`, `onCta: (() => void) | null = null`. CTA renders only when BOTH `ctaLabel` and `onCta` are set. Task 5 relies on this exact contract.

- [ ] **Step 1: Create EmptyState.svelte**

```svelte
<script lang="ts">
	// Canonical empty state (spec §4, Timeline anatomy = the canon).
	// block = view-level: icon tile + line + optional sub + optional CTA.
	// quiet = one caption line with the em-dash placeholder glyph, for card rails.
	import Icon from './Icon.svelte';
	import { Button } from '$lib/components/ui/button';

	export let title: string;
	export let variant: 'block' | 'quiet' = 'block';
	export let icon = '';
	export let sub = '';
	export let ctaLabel = '';
	export let onCta: (() => void) | null = null;
</script>

{#if variant === 'quiet'}
	<div class="py-1 text-xs text-gray-400 dark:text-gray-500">— {title}</div>
{:else}
	<div class="flex flex-col items-center gap-2.5 px-6 py-10 text-center">
		{#if icon}
			<span class="flex h-12 w-12 items-center justify-center rounded-2xl bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500">
				<Icon name={icon} size={24} />
			</span>
		{/if}
		<span class="text-sm text-gray-500 dark:text-gray-400">{title}</span>
		{#if sub}<span class="max-w-[40ch] text-xs text-gray-400 dark:text-gray-500">{sub}</span>{/if}
		{#if ctaLabel && onCta}
			<Button size="sm" class="mt-1" onclick={onCta}><Icon name="plus" size={15} /> {ctaLabel}</Button>
		{/if}
	</div>
{/if}
```

Note the icon tile is `dark:bg-gray-800` (not gray-900 like today's Timeline one-off): the primitive must stay visible on `dark:bg-gray-900` card surfaces, not just the gray-950 canvas. Intentional 1-step visual delta, listed for smoke.

- [ ] **Step 2: OverviewView view-level empty**

Add import (with the other component imports): `import EmptyState from '../ui/EmptyState.svelte';`

Replace:

```svelte
		{#if !mix.total}
			<div class="h-64 flex flex-col items-center justify-center gap-2 text-center">
				<div class="text-lg font-medium">No tasks here yet</div>
				<div class="text-sm text-gray-500">Add tasks on the board and this overview fills itself in.</div>
			</div>
		{:else}
```

with:

```svelte
		{#if !mix.total}
			<div class="h-64 flex items-center justify-center">
				<EmptyState icon="layers" title="No tasks here yet" sub="Add tasks on the board and this overview fills itself in." />
			</div>
		{:else}
```

- [ ] **Step 3: Overview cards — quiet variant**

In each file add `import EmptyState from '../../ui/EmptyState.svelte';` and swap the bare line:

`PulseCard.svelte` — replace
```svelte
			<div class="py-6 text-center text-sm text-gray-400">No activity yet.</div>
```
with
```svelte
			<div class="mt-2"><EmptyState variant="quiet" title="No activity yet" /></div>
```
(The error branch `Couldn't load activity.` is an error state, not an empty state — leave it.)

`AttentionList.svelte` — replace
```svelte
		<div class="py-6 text-center text-sm text-gray-400">Nothing needs attention.</div>
```
with
```svelte
		<div class="mt-2"><EmptyState variant="quiet" title="Nothing needs attention" /></div>
```

`TeamTable.svelte` — replace
```svelte
		<div class="py-6 text-center text-sm text-gray-400">No open tasks assigned yet.</div>
```
with
```svelte
		<div class="mt-2"><EmptyState variant="quiet" title="No open tasks assigned yet" /></div>
```

- [ ] **Step 4: MyWorkView — main list block + 4 quiet rails**

Add import: `import EmptyState from '../ui/EmptyState.svelte';`

Main list — replace
```svelte
						<div class="py-14 text-center text-sm text-gray-400">Nothing on your plate here.</div>
```
with
```svelte
						<div class="py-4"><EmptyState icon="list" title="Nothing on your plate here." /></div>
```

Workload rail — replace
```svelte
						<div class="text-xs text-gray-400">No open tasks.</div>
```
with
```svelte
						<EmptyState variant="quiet" title="No open tasks" />
```

Upcoming rail — replace
```svelte
						<div class="text-xs text-gray-400 py-1">Nothing scheduled.</div>
```
with
```svelte
						<EmptyState variant="quiet" title="Nothing scheduled" />
```

Activity rail — replace
```svelte
						<div class="text-xs text-gray-400 py-1">No recent activity.</div>
```
with
```svelte
						<EmptyState variant="quiet" title="No recent activity" />
```

Mentions rail — replace
```svelte
						<div class="text-xs text-gray-400 py-1">No mentions.</div>
```
with
```svelte
						<EmptyState variant="quiet" title="No mentions" />
```

(Quiet variant drops the trailing periods — em-dash line reads as a placeholder, not a sentence.)

- [ ] **Step 5: Verify**

Run: `npx vitest run src/lib/components/workos` → 194 passed.
Run: `npm run check` → no NEW errors mentioning `EmptyState`, `OverviewView`, `PulseCard`, `AttentionList`, `TeamTable`, `MyWorkView`.

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/workos/ui/EmptyState.svelte src/lib/components/workos/views/OverviewView.svelte src/lib/components/workos/views/overview/PulseCard.svelte src/lib/components/workos/views/overview/AttentionList.svelte src/lib/components/workos/views/overview/TeamTable.svelte src/lib/components/workos/views/MyWorkView.svelte
git commit -m "feat(workos): EmptyState primitive; Overview and My Work adopt it"
```

---

### Task 5: EmptyState view adopters — Calendar, Inbox, Timeline

**Files:**
- Modify: `src/lib/components/workos/views/CalendarView.svelte` (agenda empty, line ~200)
- Modify: `src/lib/components/workos/views/InboxView.svelte` (line ~18)
- Modify: `src/lib/components/workos/views/TimelineView.svelte` (lines ~291–309)

**Interfaces:**
- Consumes: `EmptyState` from Task 4 — `title`, `variant='block'` default, `icon`, `sub`, `ctaLabel`, `onCta` (CTA renders only when both `ctaLabel` and `onCta` are set).
- Produces: nothing.

- [ ] **Step 1: CalendarView agenda empty**

Add import: `import EmptyState from '../ui/EmptyState.svelte';`

Replace:
```svelte
			{#if !agenda.length}
				<div class="py-10 text-center text-sm text-gray-400">No scheduled tasks this month</div>
			{/if}
```
with:
```svelte
			{#if !agenda.length}
				<EmptyState icon="calendar" title="No scheduled tasks this month" sub="Tasks with due dates land here automatically." />
			{/if}
```

No CTA here — the agenda view has no add-task handler in scope; the mockup's CTA was anatomy illustration, not a wiring mandate.

- [ ] **Step 2: InboxView empty**

Add import: `import EmptyState from '../ui/EmptyState.svelte';`

Replace:
```svelte
	{#if !$notifications.length}
		<div class="p-8 text-center text-sm text-gray-400">You're all caught up.</div>
	{:else}
```
with:
```svelte
	{#if !$notifications.length}
		<EmptyState icon="inbox" title="You're all caught up" sub="Mentions and assignments will show up here." />
	{:else}
```

- [ ] **Step 3: TimelineView — swap the one-off rich empty state to the primitive**

Add import: `import EmptyState from '../ui/EmptyState.svelte';`

Replace the inner content (keep the outer sticky positioning `<div class="flex-1 sticky left-0 z-10 …">` exactly as is):

```svelte
						<div class="flex-1 sticky left-0 z-10 flex items-center justify-center py-16" style="width: {scrollerW || 600}px;">
							<div class="flex flex-col items-center gap-2.5 text-center px-6">
								<span class="w-12 h-12 rounded-2xl bg-gray-100 dark:bg-gray-900 text-gray-400 dark:text-gray-500 flex items-center justify-center">
									<Icon name="chart-gantt" size={24} />
								</span>
								{#if unscheduled.length}
									<span class="text-sm text-gray-500 dark:text-gray-400">Nothing scheduled yet</span>
									<span class="text-xs text-gray-400 dark:text-gray-500">Drag a task in from the Unscheduled panel, or give a task dates.</span>
								{:else}
									<span class="text-sm text-gray-500 dark:text-gray-400">No tasks on the timeline</span>
									<span class="text-xs text-gray-400 dark:text-gray-500">Plan your work by creating a task — it lands on today.</span>
									<button class="mt-1 inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground text-sm font-medium" onclick={() => { addingRow = true; rowTitle = ''; }}>
										<Icon name="plus" size={15} /> Add task
									</button>
								{/if}
							</div>
						</div>
```

with:

```svelte
						<div class="flex-1 sticky left-0 z-10 flex items-center justify-center py-16" style="width: {scrollerW || 600}px;">
							{#if unscheduled.length}
								<EmptyState icon="chart-gantt" title="Nothing scheduled yet" sub="Drag a task in from the Unscheduled panel, or give a task dates." />
							{:else}
								<EmptyState
									icon="chart-gantt"
									title="No tasks on the timeline"
									sub="Plan your work by creating a task — it lands on today."
									ctaLabel="Add task"
									onCta={() => { addingRow = true; rowTitle = ''; }}
								/>
							{/if}
						</div>
```

The hand-rolled CTA button becomes the shadcn `Button size="sm"` inside EmptyState — same primary fill, standard focus ring (P2b convention). If `Icon` becomes unused in TimelineView after this swap, leave the import ONLY if other usages remain (check with grep first: `rg 'Icon' src/lib/components/workos/views/TimelineView.svelte`); remove the import if this was the last usage.

- [ ] **Step 4: Verify**

Run: `npx vitest run src/lib/components/workos` → 194 passed.
Run: `npm run check` → no NEW errors mentioning `CalendarView`, `InboxView`, `TimelineView`.
Run: `rg 'py-10 text-center|p-8 text-center|py-14 text-center|py-6 text-center text-sm text-gray-400' src/lib/components/workos/views` → remaining hits must be error/loading states only (e.g. "Couldn't load activity"), not empty states.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/views/CalendarView.svelte src/lib/components/workos/views/InboxView.svelte src/lib/components/workos/views/TimelineView.svelte
git commit -m "refactor(workos): Calendar, Inbox and Timeline adopt EmptyState"
```

---

## Wave-completion verification (final review runs these)

```
rg '#101623|#1b2434|#232f45|#7e8aa0|#9aa6ba|#aab5c8|#2a3651|#123c2c|#3c1a1a|#8fa3ff|#f0b47a|#f27d72|#5DCAA5' src/lib/components/workos   # → 0
rg 'text-\[22px\]|text-\[34px\]' src/lib/components/workos                                                                                # → 0
rg 'wos-display' src/lib/components/workos --files-with-matches                                                                           # → KpiNumeral.svelte + styles.css (the class definition) only
npx vitest run src/lib/components/workos                                                                                                  # → 194 passed
npm run check                                                                                                                             # → no new workos errors
```

## Intentional visual deltas (fold into the consolidated smoke checklist)

1. Overview KPI band: dark ink panel → standard themed card, both modes. Numerals 22→28px. Dots: due `#f0b47a`→amber `#f59e0b`, overdue `#f27d72`→red `#dc2626` (dark `#f87171`), completed `#5DCAA5`→green `#769a4a`, new-tasks periwinkle→gray-500. Week toggle now primary-filled pill segment.
2. Completed-delta on the band + Momentum completion delta + My Work done-delta: all now the tinted DeltaBadge pill (green/red, arrow icon).
3. My Work stat numerals 34→28px (weight stays 700); sub-labels lose `font-mono`.
4. Momentum completion delta: green badge now points DOWN when faster (was ▾ glyph, same direction — now a pill).
5. Empty states: Calendar/Inbox gain icon tiles; Timeline's icon tile background lightens one step in dark mode (gray-900→gray-800); My Work rails + Overview cards switch to left-aligned quiet "— {text}" lines (were centered sentences).
6. Overview view-level empty ("No tasks here yet") now has the layers icon tile, title drops to 14px.
