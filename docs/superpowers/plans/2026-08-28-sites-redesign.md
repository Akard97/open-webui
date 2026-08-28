# Sites Tool UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Sites tool UI as a centered two-column workbench (site rail + tabbed detail panel with inline create), replacing the `SiteEditor` modal, per `docs/superpowers/specs/2026-08-28-sites-redesign-design.md`.

**Architecture:** `SitesPage.svelte` owns all state (sites list, selection, tab, view/create mode) and renders `SiteRail` + either `SiteDetail` (header + 5 tab components) or `CreatePanel`. Pure logic lives in `lib/form.ts` and `lib/selection.ts` with vitest coverage (repo convention: logic tests only, no component tests). Backend and API client are untouched.

**Tech Stack:** Svelte 5 runes, Tailwind (+ scoped CSS token block `sites.css`), vitest, existing APIs in `src/lib/apis/sites`, `dayjs` relativeTime, `svelte-sonner` toasts.

## Global Constraints

- Frontend only — do NOT touch `backend/`, `src/lib/apis/sites/index.ts`, or migrations.
- All user-facing strings through `$i18n.t('...')` (context `i18n`, same as current components).
- Svelte 5 runes mode (`$state`, `$props`, `$derived`, `$effect`) — match existing sites components.
- Colors only via the `.sites-root` CSS tokens defined in Task 3 (spec §4); dark theme via `.dark .sites-root`.
- Motion rules (spec §5): transitions name exact properties (never `transition: all`); pressables scale(0.97) active, 140ms; pane enter 180ms `cubic-bezier(0.23,1,0.32,1)`; hover FX gated behind `@media (hover:hover) and (pointer:fine)`; respect `prefers-reduced-motion`.
- Slugs, URLs, filenames in `font-mono`; stat numerals `tabular-nums`.
- Verification commands: `npm run test:frontend -- --run src/lib/components/sites` and `npm run check`. `npm run check` must not add NEW errors over baseline (run it once before Task 1 and note the baseline count).
- Do NOT start a Vite dev server (standing user rule). Browser smoke is a separate post-plan step done by the user.
- Commits: `feat(sites): …` / `refactor(sites): …`, one per task step where the plan says commit.

**Files created:** `src/lib/components/sites/lib/form.ts`, `lib/form.test.ts`, `lib/selection.ts`, `lib/selection.test.ts`, `sites.css`, `FileDrop.svelte`, `VisibilityPicker.svelte`, `SiteRail.svelte`, `SiteDetail.svelte`, `CreatePanel.svelte`, `tabs/OverviewTab.svelte`, `tabs/FilesTab.svelte`, `tabs/SettingsTab.svelte`, `tabs/AnalyticsTab.svelte`, `tabs/VersionsTab.svelte`.
**Files rewritten:** `src/lib/components/sites/SitesPage.svelte`.
**Files deleted:** `src/lib/components/sites/SiteEditor.svelte` (Task 11 only — app must compile after every task).

---

### Task 1: Form logic library (`lib/form.ts`)

**Files:**
- Create: `src/lib/components/sites/lib/form.ts`
- Test: `src/lib/components/sites/lib/form.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces (used by Tasks 6, 7, 9, and 5):
  - `slugify(v: string): string`
  - `htmlFileNames(names: string[]): string[]`
  - `pickEntryFile(htmlNames: string[], current: string): string`
  - `mergeFiles<T extends { name: string }>(existing: T[], incoming: T[]): T[]`
  - `grantsForLevel(level: string, specificGrants: any[]): any[]`
  - `totalSize(files: { size?: number }[]): number`
  - `formatSize(bytes: number): string`

- [ ] **Step 1: Write the failing tests**

```ts
// src/lib/components/sites/lib/form.test.ts
import { describe, expect, it } from 'vitest';
import {
	slugify,
	htmlFileNames,
	pickEntryFile,
	mergeFiles,
	grantsForLevel,
	totalSize,
	formatSize
} from './form';

describe('slugify', () => {
	it('lowercases and dashes non-alphanumerics', () => {
		expect(slugify('My Cool Page!')).toBe('my-cool-page');
	});
	it('trims leading/trailing dashes and caps at 60 chars', () => {
		expect(slugify('--Hello--')).toBe('hello');
		expect(slugify('a'.repeat(80))).toHaveLength(60);
	});
});

describe('htmlFileNames', () => {
	it('keeps .html and .htm case-insensitively', () => {
		expect(htmlFileNames(['a.HTML', 'b.htm', 'c.css', 'd.html.map'])).toEqual(['a.HTML', 'b.htm']);
	});
});

describe('pickEntryFile', () => {
	it('keeps current when still present', () => {
		expect(pickEntryFile(['a.html', 'b.html'], 'b.html')).toBe('b.html');
	});
	it('prefers index.html when current is gone', () => {
		expect(pickEntryFile(['a.html', 'index.html'], 'gone.html')).toBe('index.html');
	});
	it('falls back to first html', () => {
		expect(pickEntryFile(['a.html', 'b.html'], '')).toBe('a.html');
	});
	it('returns current unchanged when no html files', () => {
		expect(pickEntryFile([], 'x.html')).toBe('x.html');
	});
});

describe('mergeFiles', () => {
	it('appends new names, keeps first occurrence on duplicates', () => {
		const a = { name: 'a.html', v: 1 };
		expect(mergeFiles([a], [{ name: 'a.html', v: 2 } as any, { name: 'b.css', v: 3 } as any])).toEqual(
			[a, { name: 'b.css', v: 3 }]
		);
	});
});

describe('grantsForLevel', () => {
	const wild = { principal_type: 'user', principal_id: '*', permission: 'read' };
	const g = { principal_type: 'user', principal_id: 'u1', permission: 'read' };
	it('internal → single wildcard grant', () => {
		expect(grantsForLevel('internal', [g])).toEqual([wild]);
	});
	it('specific → passes grants through minus wildcard', () => {
		expect(grantsForLevel('specific', [g, wild])).toEqual([g]);
	});
	it('public and private → empty', () => {
		expect(grantsForLevel('public', [g])).toEqual([]);
		expect(grantsForLevel('private', [g])).toEqual([]);
	});
});

describe('totalSize / formatSize', () => {
	it('sums sizes, tolerating missing size', () => {
		expect(totalSize([{ size: 1000 }, {}, { size: 24 }])).toBe(1024);
	});
	it('formats B, KB, MB with one decimal', () => {
		expect(formatSize(512)).toBe('512 B');
		expect(formatSize(20172)).toBe('19.7 KB');
		expect(formatSize(3 * 1024 * 1024)).toBe('3.0 MB');
	});
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test:frontend -- --run src/lib/components/sites/lib/form.test.ts`
Expected: FAIL — cannot resolve `./form`.

- [ ] **Step 3: Implement `form.ts`**

```ts
// src/lib/components/sites/lib/form.ts
import { isEveryoneGrant } from './access';

export const slugify = (v: string): string =>
	v
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '')
		.slice(0, 60);

export const htmlFileNames = (names: string[]): string[] =>
	names.filter((n) => /\.html?$/i.test(n));

export const pickEntryFile = (htmlNames: string[], current: string): string => {
	if (htmlNames.length === 0 || htmlNames.includes(current)) return current;
	return htmlNames.includes('index.html') ? 'index.html' : htmlNames[0];
};

export const mergeFiles = <T extends { name: string }>(existing: T[], incoming: T[]): T[] => {
	const next = [...existing];
	for (const f of incoming) {
		if (!next.some((x) => x.name === f.name)) next.push(f);
	}
	return next;
};

export const grantsForLevel = (level: string, specificGrants: any[]): any[] => {
	if (level === 'internal')
		return [{ principal_type: 'user', principal_id: '*', permission: 'read' }];
	if (level === 'specific') return specificGrants.filter((g) => !isEveryoneGrant(g));
	return [];
};

export const totalSize = (files: { size?: number }[]): number =>
	files.reduce((acc, f) => acc + (f.size ?? 0), 0);

export const formatSize = (bytes: number): string => {
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
	return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test:frontend -- --run src/lib/components/sites/lib/form.test.ts`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/sites/lib/form.ts src/lib/components/sites/lib/form.test.ts
git commit -m "feat(sites): extract form logic into tested lib for redesign"
```

---

### Task 2: Selection logic (`lib/selection.ts`)

**Files:**
- Create: `src/lib/components/sites/lib/selection.ts`
- Test: `src/lib/components/sites/lib/selection.test.ts`

**Interfaces:**
- Produces (used by Task 11): `nextSelection(sites: { id: string }[], removedId: string): string | null` — call with the PRE-delete list; returns the id to select after `removedId` is removed.

- [ ] **Step 1: Write the failing tests**

```ts
// src/lib/components/sites/lib/selection.test.ts
import { describe, expect, it } from 'vitest';
import { nextSelection } from './selection';

const s = (id: string) => ({ id });

describe('nextSelection', () => {
	it('selects the item that takes the removed slot', () => {
		expect(nextSelection([s('a'), s('b'), s('c')], 'b')).toBe('c');
	});
	it('selects previous when removing the last item', () => {
		expect(nextSelection([s('a'), s('b')], 'b')).toBe('a');
	});
	it('returns null when removing the only item', () => {
		expect(nextSelection([s('a')], 'a')).toBeNull();
	});
	it('returns first id when removedId not found', () => {
		expect(nextSelection([s('a'), s('b')], 'zz')).toBe('a');
	});
	it('returns null for empty list', () => {
		expect(nextSelection([], 'a')).toBeNull();
	});
});
```

- [ ] **Step 2: Run to verify FAIL**

Run: `npm run test:frontend -- --run src/lib/components/sites/lib/selection.test.ts`
Expected: FAIL — cannot resolve `./selection`.

- [ ] **Step 3: Implement**

```ts
// src/lib/components/sites/lib/selection.ts
export const nextSelection = (
	sites: { id: string }[],
	removedId: string
): string | null => {
	const idx = sites.findIndex((s) => s.id === removedId);
	const remaining = sites.filter((s) => s.id !== removedId);
	if (remaining.length === 0) return null;
	if (idx === -1) return remaining[0].id;
	return remaining[Math.min(idx, remaining.length - 1)].id;
};
```

- [ ] **Step 4: Run to verify PASS**

Run: `npm run test:frontend -- --run src/lib/components/sites/lib/selection.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/sites/lib/selection.ts src/lib/components/sites/lib/selection.test.ts
git commit -m "feat(sites): selection logic for delete-selects-next"
```

---

### Task 3: Design tokens + shared subcomponents (`sites.css`, `FileDrop`, `VisibilityPicker`)

**Files:**
- Create: `src/lib/components/sites/sites.css`
- Create: `src/lib/components/sites/FileDrop.svelte`
- Create: `src/lib/components/sites/VisibilityPicker.svelte`

**Interfaces:**
- Produces:
  - CSS classes on `.sites-root` scope: tokens (`--st-*`), `.st-press`, `.st-pane`, `.st-btn`, `.st-btn-primary`, `.st-btn-danger`, `.st-chip`, `.st-chip-pub`, `.st-pv`, `.st-dot`, `.st-dot-off`, `.st-status`.
  - `FileDrop.svelte` props: `{ label: string, onFiles: (files: File[]) => void }`.
  - `VisibilityPicker.svelte` props: `{ level: string ($bindable), accessGrants: any[] ($bindable) }` — levels `'private' | 'specific' | 'internal' | 'public'`.

- [ ] **Step 1: Write `sites.css`**

```css
/* Sites tool tokens + shared motion. Scope: .sites-root. Spec §4–5. */
.sites-root {
	--st-ground: #f7f9f9;
	--st-card: #ffffff;
	--st-ink: #16282d;
	--st-deep: #00353e;
	--st-muted: #5d7176;
	--st-faint: #8fa0a4;
	--st-border: #e2e9ea;
	--st-hairline: #edf2f3;
	--st-hover: #f1f5f5;
	--st-accent: #00677f;
	--st-accent-ink: #ffffff;
	--st-accent-soft: #e3f1f4;
	--st-accent-soft-ink: #00566a;
	--st-live: #789d4a;
	--st-live-soft: #eef4e4;
	--st-danger: #c2410c;
	--st-danger-soft: #fdf0e8;
	--st-chart: #00a9ce;
	--st-chart-fill: rgba(0, 169, 206, 0.12);
	--st-shadow: 0 1px 2px rgba(0, 53, 62, 0.05), 0 4px 16px rgba(0, 53, 62, 0.05);
	--st-ease-out: cubic-bezier(0.23, 1, 0.32, 1);
	color: var(--st-ink);
}
.dark .sites-root {
	--st-ground: #0b1416;
	--st-card: #111c1f;
	--st-ink: #e4edee;
	--st-deep: #bfe9f1;
	--st-muted: #93a6aa;
	--st-faint: #5f7478;
	--st-border: #223236;
	--st-hairline: #1a282b;
	--st-hover: #162225;
	--st-accent: #2fb8cf;
	--st-accent-ink: #03252c;
	--st-accent-soft: #123239;
	--st-accent-soft-ink: #7fd4e4;
	--st-live: #9dc06a;
	--st-live-soft: #1e2a14;
	--st-danger: #f0824d;
	--st-danger-soft: #33200f;
	--st-chart: #2fb8cf;
	--st-chart-fill: rgba(47, 184, 207, 0.14);
	--st-shadow: 0 1px 2px rgba(0, 0, 0, 0.3), 0 4px 16px rgba(0, 0, 0, 0.25);
}

.sites-root .st-press {
	transition: transform 140ms var(--st-ease-out);
}
.sites-root .st-press:active {
	transform: scale(0.97);
}

.sites-root .st-pane {
	animation: st-enter 180ms var(--st-ease-out);
}
@keyframes st-enter {
	from {
		opacity: 0;
		transform: translateY(4px);
	}
	to {
		opacity: 1;
		transform: translateY(0);
	}
}

.sites-root .st-btn {
	border: 1px solid var(--st-border);
	border-radius: 9px;
	padding: 6px 13px;
	font-size: 13px;
	font-weight: 500;
	background: var(--st-card);
	transition: background 120ms ease, transform 140ms var(--st-ease-out);
}
.sites-root .st-btn:active {
	transform: scale(0.97);
}
.sites-root .st-btn-primary {
	background: var(--st-accent);
	border-color: var(--st-accent);
	color: var(--st-accent-ink);
	font-weight: 600;
}
.sites-root .st-btn-danger {
	color: var(--st-danger);
	border-color: color-mix(in oklab, var(--st-danger) 40%, transparent);
}
@media (hover: hover) and (pointer: fine) {
	.sites-root .st-btn:hover {
		background: var(--st-hover);
	}
	.sites-root .st-btn-primary:hover {
		background: var(--st-accent);
		filter: brightness(1.08);
	}
	.sites-root .st-btn-danger:hover {
		background: var(--st-danger-soft);
	}
}

.sites-root .st-chip {
	font-size: 10px;
	font-weight: 600;
	letter-spacing: 0.04em;
	padding: 2px 7px;
	border-radius: 99px;
	background: var(--st-hairline);
	color: var(--st-muted);
	flex: none;
}
.sites-root .st-chip-pub {
	background: var(--st-live-soft);
	color: var(--st-live);
}
.sites-root .st-pv {
	font-size: 9.5px;
	font-weight: 700;
	letter-spacing: 0.05em;
	padding: 1.5px 6px;
	border-radius: 99px;
	background: var(--st-accent-soft);
	color: var(--st-accent-soft-ink);
}
.sites-root .st-dot {
	width: 7px;
	height: 7px;
	border-radius: 50%;
	background: var(--st-live);
	flex: none;
}
.sites-root .st-dot-off {
	background: var(--st-faint);
}
.sites-root .st-status {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	font-size: 11.5px;
	font-weight: 600;
	color: var(--st-live);
	background: var(--st-live-soft);
	border-radius: 99px;
	padding: 3px 10px;
}
.sites-root .st-status .st-dot {
	animation: st-pulse 2.4s ease-in-out infinite;
}
@keyframes st-pulse {
	0%,
	100% {
		opacity: 1;
	}
	50% {
		opacity: 0.45;
	}
}

@media (prefers-reduced-motion: reduce) {
	.sites-root .st-pane {
		animation: none;
	}
	.sites-root .st-status .st-dot {
		animation: none;
	}
	.sites-root .st-press,
	.sites-root .st-btn {
		transition: none;
	}
}
```

- [ ] **Step 2: Write `FileDrop.svelte`**

```svelte
<script lang="ts">
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	let {
		label,
		onFiles
	}: { label: string; onFiles: (files: File[]) => void } = $props();

	let dragging = $state(false);
	let inputEl: HTMLInputElement | undefined = $state();
</script>

<button
	type="button"
	class="w-full rounded-xl border-[1.5px] border-dashed px-6 py-7 text-center text-[13px] transition-colors duration-150
		{dragging
		? 'border-[var(--st-accent)] bg-[var(--st-accent-soft)] text-[var(--st-accent-soft-ink)]'
		: 'border-[var(--st-border)] text-[var(--st-muted)]'}"
	ondragover={(e) => {
		e.preventDefault();
		dragging = true;
	}}
	ondragleave={() => (dragging = false)}
	ondrop={(e) => {
		e.preventDefault();
		dragging = false;
		onFiles(Array.from(e.dataTransfer?.files ?? []));
	}}
	onclick={() => inputEl?.click()}
>
	{label}
</button>
<input
	bind:this={inputEl}
	type="file"
	multiple
	hidden
	aria-label={$i18n.t('Choose files')}
	onchange={(e) => {
		const t = e.target as HTMLInputElement;
		onFiles(Array.from(t.files ?? []));
		t.value = '';
	}}
/>
```

- [ ] **Step 3: Write `VisibilityPicker.svelte`**

```svelte
<script lang="ts">
	import { getContext } from 'svelte';
	import AccessControl from '$lib/components/workspace/common/AccessControl.svelte';

	const i18n = getContext('i18n');

	let { level = $bindable('private'), accessGrants = $bindable([]) } = $props();

	const options = $derived([
		{ value: 'private', title: $i18n.t('Only me'), sub: $i18n.t('Private link — just for you') },
		{
			value: 'specific',
			title: $i18n.t('Specific people or groups'),
			sub: $i18n.t('Pick who can open the link')
		},
		{
			value: 'internal',
			title: $i18n.t('Everyone with an account'),
			sub: $i18n.t('Anyone signed in')
		},
		{
			value: 'public',
			title: $i18n.t('Public — no login needed'),
			sub: $i18n.t('Anyone with the link')
		}
	]);
</script>

<div class="flex max-w-md flex-col gap-1.5" role="radiogroup" aria-label={$i18n.t('Who can view')}>
	{#each options as o (o.value)}
		<label
			class="flex cursor-pointer items-center gap-2.5 rounded-[10px] border px-3 py-2.5 text-[13.5px] transition-colors duration-150
				{level === o.value
				? 'border-[var(--st-accent)] bg-[var(--st-accent-soft)]'
				: 'border-[var(--st-hairline)]'}"
		>
			<input type="radio" name="site-level" value={o.value} bind:group={level} />
			<span>
				{o.title}
				<span class="block text-[11.5px] text-[var(--st-muted)]">{o.sub}</span>
			</span>
		</label>
	{/each}
</div>
{#if level === 'specific'}
	<div class="mt-2 max-w-md">
		<AccessControl
			bind:accessGrants
			accessRoles={['read']}
			sharePublic={false}
			showVisibilitySelect={false}
		/>
	</div>
{/if}
```

- [ ] **Step 4: Verify compile**

Run: `npm run check`
Expected: no NEW errors vs baseline (components not yet imported anywhere; svelte-check still parses them).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/sites/sites.css src/lib/components/sites/FileDrop.svelte src/lib/components/sites/VisibilityPicker.svelte
git commit -m "feat(sites): design tokens + FileDrop/VisibilityPicker shared components"
```

---

### Task 4: `SiteRail.svelte`

**Files:**
- Create: `src/lib/components/sites/SiteRail.svelte`

**Interfaces:**
- Consumes: `siteAccessLevel` from `./lib/access`; classes from `sites.css` (imported by page in Task 11).
- Produces props: `{ sites: any[], selectedId: string | null, creating: boolean, showAll: boolean, isAdmin: boolean, onSelect: (id: string) => void, onCreate: () => void, onToggleAll: (showAll: boolean) => void }`.

- [ ] **Step 1: Write the component**

```svelte
<script lang="ts">
	import { getContext } from 'svelte';
	import { siteAccessLevel } from './lib/access';

	const i18n = getContext('i18n');

	let {
		sites = [],
		selectedId = null,
		creating = false,
		showAll = false,
		isAdmin = false,
		onSelect = (_id: string) => {},
		onCreate = () => {},
		onToggleAll = (_v: boolean) => {}
	} = $props();

	const levelBadge = (s: any) => {
		const labels: Record<string, string> = {
			public: $i18n.t('Public'),
			internal: $i18n.t('Everyone'),
			specific: $i18n.t('Specific'),
			private: $i18n.t('Private')
		};
		return labels[siteAccessLevel(s)];
	};
</script>

<aside
	class="flex flex-col border-b border-[var(--st-hairline)] bg-[color-mix(in_oklab,var(--st-card)_60%,var(--st-ground))] md:border-b-0 md:border-r"
>
	<div class="flex flex-col gap-2.5 px-3.5 pb-2.5 pt-4">
		<button
			type="button"
			class="st-press flex items-center justify-center gap-1.5 rounded-[10px] bg-[var(--st-accent)] px-3 py-2 text-[13.5px] font-semibold text-[var(--st-accent-ink)]"
			onclick={onCreate}
		>
			＋ {$i18n.t('New site')}
		</button>
		{#if isAdmin}
			<div class="flex rounded-lg bg-[var(--st-hairline)] p-0.5 text-xs">
				{#each [[false, $i18n.t('My sites')], [true, $i18n.t('All users')]] as [value, label] (label)}
					<button
						type="button"
						class="flex-1 rounded-md px-2 py-1 font-medium transition-colors duration-150
							{showAll === value
							? 'bg-[var(--st-card)] text-[var(--st-ink)] shadow-sm'
							: 'text-[var(--st-muted)]'}"
						onclick={() => onToggleAll(value as boolean)}>{label}</button
					>
				{/each}
			</div>
		{/if}
	</div>
	<nav class="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 pb-3.5 pt-1">
		<div
			class="px-2 pb-1.5 pt-2 text-[11px] font-semibold uppercase tracking-[0.07em] text-[var(--st-faint)]"
		>
			{$i18n.t('Published')} · {sites.length}
		</div>
		{#each sites as s (s.id)}
			<button
				type="button"
				class="flex w-full flex-col gap-0.5 rounded-[10px] border px-2.5 py-2 text-left transition-colors duration-150
					{s.id === selectedId && !creating
					? 'border-[color-mix(in_oklab,var(--st-accent)_25%,transparent)] bg-[var(--st-accent-soft)]'
					: 'border-transparent'}"
				onclick={() => onSelect(s.id)}
			>
				<span class="flex min-w-0 items-center gap-1.5">
					<span class="st-dot {siteAccessLevel(s) === 'private' ? 'st-dot-off' : ''}"></span>
					<span
						class="truncate text-[13.5px] font-semibold {s.id === selectedId && !creating
							? 'text-[var(--st-accent-soft-ink)]'
							: ''}">{s.name}</span
					>
					<span class="st-chip ml-auto {siteAccessLevel(s) === 'public' ? 'st-chip-pub' : ''}"
						>{levelBadge(s)}</span
					>
				</span>
				<span class="font-mono text-[11.5px] text-[var(--st-faint)]">/sites/{s.slug}</span>
				{#if showAll && s.user_name}
					<span class="text-[10px] text-[var(--st-faint)]">{s.user_name}</span>
				{/if}
			</button>
		{/each}
	</nav>
</aside>
```

- [ ] **Step 2: Verify compile**

Run: `npm run check`
Expected: no NEW errors vs baseline.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/sites/SiteRail.svelte
git commit -m "feat(sites): SiteRail list component"
```

---

### Task 5: `tabs/OverviewTab.svelte`

**Files:**
- Create: `src/lib/components/sites/tabs/OverviewTab.svelte`

**Interfaces:**
- Consumes: `totalSize`, `formatSize` from `../lib/form`; `siteAccessLevel` from `../lib/access`; `copyToClipboard` from `$lib/utils`.
- Produces props: `{ site: any, onGoTab: (tab: string) => void }`. Tab names it emits: `'files' | 'settings' | 'versions'`.

- [ ] **Step 1: Write the component**

```svelte
<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import dayjs from 'dayjs';
	import relativeTime from 'dayjs/plugin/relativeTime';
	import { copyToClipboard } from '$lib/utils';
	import { siteAccessLevel } from '../lib/access';
	import { totalSize, formatSize } from '../lib/form';

	dayjs.extend(relativeTime);

	const i18n = getContext('i18n');

	let { site, onGoTab = (_t: string) => {} } = $props();

	const url = $derived(`${window.location.origin}/sites/${site.slug}/`);
	const level = $derived(siteAccessLevel(site));

	const visLabel = $derived(
		{
			public: $i18n.t('Public'),
			internal: $i18n.t('Everyone'),
			specific: $i18n.t('Specific'),
			private: $i18n.t('Private')
		}[level]
	);
	const visSub = $derived(
		{
			public: $i18n.t('No login needed'),
			internal: $i18n.t('Signed-in viewers'),
			specific: $i18n.t('Signed-in viewers'),
			private: $i18n.t('Only you')
		}[level]
	);

	const copy = async () => {
		await copyToClipboard(url);
		toast.success($i18n.t('Link copied'));
	};
</script>

<div class="st-pane flex flex-col gap-4">
	<div
		class="flex flex-wrap items-center gap-3 rounded-xl border border-[var(--st-border)] bg-gradient-to-r from-[color-mix(in_oklab,var(--st-accent-soft)_70%,var(--st-card))] via-[var(--st-card)] to-[var(--st-card)] px-4 py-3.5"
	>
		<span class="min-w-0 flex-1 truncate font-mono text-[13.5px] text-[var(--st-accent-soft-ink)]"
			>{url}</span
		>
		<div class="flex gap-2">
			<button type="button" class="st-btn" onclick={copy}>{$i18n.t('Copy link')}</button>
			<a class="st-btn st-btn-primary inline-flex items-center" href={url} target="_blank" rel="noopener"
				>{$i18n.t('Open site')} ↗</a
			>
		</div>
	</div>

	<div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
		<div class="rounded-xl border border-[var(--st-hairline)] px-3.5 py-3">
			<div
				class="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--st-faint)]"
			>
				{$i18n.t('Views · 7d')} <span class="st-pv">{$i18n.t('PREVIEW')}</span>
			</div>
			<div class="mt-0.5 text-[21px] font-bold tabular-nums tracking-tight">1,284</div>
			<div class="text-[11.5px] text-[var(--st-muted)]">{$i18n.t('Sample data')}</div>
		</div>
		<div class="rounded-xl border border-[var(--st-hairline)] px-3.5 py-3">
			<div class="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--st-faint)]">
				{$i18n.t('Files')}
			</div>
			<div class="mt-0.5 text-[21px] font-bold tabular-nums tracking-tight">
				{(site.files ?? []).length}
			</div>
			<div class="text-[11.5px] text-[var(--st-muted)]">
				{formatSize(totalSize(site.files ?? []))}
				{$i18n.t('total')}
			</div>
		</div>
		<div class="rounded-xl border border-[var(--st-hairline)] px-3.5 py-3">
			<div class="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--st-faint)]">
				{$i18n.t('Visibility')}
			</div>
			<div class="mt-1 text-[16px] font-bold tracking-tight">{visLabel}</div>
			<div class="text-[11.5px] text-[var(--st-muted)]">{visSub}</div>
		</div>
		<div class="rounded-xl border border-[var(--st-hairline)] px-3.5 py-3">
			<div class="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--st-faint)]">
				{$i18n.t('Updated')}
			</div>
			<div class="mt-1 text-[16px] font-bold tracking-tight">
				{dayjs(site.updated_at * 1000).fromNow()}
			</div>
			<div class="text-[11.5px] text-[var(--st-muted)]">
				{$i18n.t('Created')} {dayjs(site.created_at * 1000).format('MMM D, YYYY')}
			</div>
		</div>
	</div>

	<div class="grid grid-cols-1 gap-3 md:grid-cols-2">
		<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-3.5">
			<h4
				class="mb-2 text-[12px] font-semibold uppercase tracking-[0.06em] text-[var(--st-faint)]"
			>
				{$i18n.t('Details')}
			</h4>
			<div
				class="flex justify-between border-b border-[var(--st-hairline)] py-1.5 text-[13px]"
			>
				<span class="text-[var(--st-muted)]">{$i18n.t('Entry file')}</span>
				<span class="font-mono">{site.entry_file}</span>
			</div>
			<div class="flex justify-between py-1.5 text-[13px]">
				<span class="text-[var(--st-muted)]">{$i18n.t('Owner')}</span>
				<span>{site.user_name ?? $i18n.t('You')}</span>
			</div>
		</div>
		<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-3.5">
			<h4
				class="mb-2 text-[12px] font-semibold uppercase tracking-[0.06em] text-[var(--st-faint)]"
			>
				{$i18n.t('Quick actions')}
			</h4>
			{#each [[$i18n.t('Replace files'), $i18n.t('Go to Files'), 'files'], [$i18n.t('Change who can view'), $i18n.t('Go to Settings'), 'settings'], [$i18n.t('Restore an older version'), $i18n.t('Go to Versions'), 'versions']] as [label, cta, tab], i (tab)}
				<div
					class="flex items-center justify-between py-1.5 text-[13px] {i < 2
						? 'border-b border-[var(--st-hairline)]'
						: ''}"
				>
					<span class="text-[var(--st-muted)]">{label}</span>
					<button
						type="button"
						class="st-press rounded-[7px] px-2 py-1 text-xs text-[var(--st-muted)] hover:bg-[var(--st-hover)] hover:text-[var(--st-ink)]"
						onclick={() => onGoTab(tab as string)}>{cta} →</button
					>
				</div>
			{/each}
		</div>
	</div>
</div>
```

- [ ] **Step 2: Verify compile**

Run: `npm run check`
Expected: no NEW errors vs baseline.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/sites/tabs/OverviewTab.svelte
git commit -m "feat(sites): Overview tab"
```

---

### Task 6: `tabs/FilesTab.svelte`

**Files:**
- Create: `src/lib/components/sites/tabs/FilesTab.svelte`

**Interfaces:**
- Consumes: `FileDrop.svelte` (Task 3), `htmlFileNames` / `pickEntryFile` / `mergeFiles` / `formatSize` from `../lib/form`, `updateSite` from `$lib/apis/sites`.
- Produces props: `{ site: any, onSaved: () => void }`. Publishing sends `name`/`slug` unchanged plus staged `files` and `entry_file` (backend supports entry-only updates).

- [ ] **Step 1: Write the component**

```svelte
<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { updateSite } from '$lib/apis/sites';
	import FileDrop from '../FileDrop.svelte';
	import { htmlFileNames, pickEntryFile, mergeFiles, formatSize } from '../lib/form';

	const i18n = getContext('i18n');

	let { site, onSaved = () => {} } = $props();

	let staged = $state<File[]>([]);
	let entryFile = $state('');
	let saving = $state(false);

	$effect(() => {
		// reset staged state whenever the selected site changes
		site.id;
		staged = [];
		entryFile = site.entry_file ?? '';
	});

	const htmlNames = $derived(
		staged.length > 0
			? htmlFileNames(staged.map((f) => f.name))
			: htmlFileNames((site.files ?? []).map((f: any) => f.name))
	);

	$effect(() => {
		entryFile = pickEntryFile(htmlNames, entryFile);
	});

	const dirty = $derived(staged.length > 0 || entryFile !== site.entry_file);

	const publish = async () => {
		saving = true;
		try {
			const fd = new FormData();
			fd.append('name', site.name);
			fd.append('slug', site.slug);
			if (entryFile) fd.append('entry_file', entryFile);
			for (const f of staged) fd.append('files', f);
			await updateSite(localStorage.token, site.id, fd);
			toast.success($i18n.t('Site saved'));
			staged = [];
			onSaved();
		} catch (err) {
			toast.error(`${err}`);
		} finally {
			saving = false;
		}
	};
</script>

<div class="st-pane flex flex-col gap-3.5">
	<FileDrop
		label={staged.length === 0
			? $i18n.t('Drop files to replace the current ones, or click to browse')
			: $i18n.t('Drop more files, or click to browse')}
		onFiles={(files) => (staged = mergeFiles(staged, files))}
	/>

	<div class="overflow-hidden rounded-xl border border-[var(--st-hairline)]">
		{#if staged.length > 0}
			{#each staged as f (f.name)}
				<div
					class="flex items-center gap-2.5 border-b border-[var(--st-hairline)] px-3 py-2 text-[13px] last:border-b-0"
				>
					<span class="min-w-0 flex-1 truncate font-mono">{f.name}</span>
					{#if f.name === entryFile}<span class="st-pv">{$i18n.t('ENTRY')}</span>{/if}
					<span class="text-xs tabular-nums text-[var(--st-faint)]">{formatSize(f.size)}</span>
					<button
						type="button"
						class="st-press rounded px-1.5 text-[var(--st-faint)] hover:text-[var(--st-danger)]"
						aria-label={$i18n.t('Remove file')}
						onclick={() => (staged = staged.filter((x) => x.name !== f.name))}>✕</button
					>
				</div>
			{/each}
		{:else}
			{#each site.files ?? [] as f (f.name)}
				<div
					class="flex items-center gap-2.5 border-b border-[var(--st-hairline)] px-3 py-2 text-[13px] last:border-b-0"
				>
					<span class="min-w-0 flex-1 truncate font-mono">{f.name}</span>
					{#if f.name === entryFile}<span class="st-pv">{$i18n.t('ENTRY')}</span>{/if}
					<span class="text-xs tabular-nums text-[var(--st-faint)]"
						>{f.size != null ? formatSize(f.size) : ''}</span
					>
				</div>
			{/each}
		{/if}
	</div>
	{#if staged.length > 0}
		<div class="text-xs text-[var(--st-faint)]">
			{$i18n.t('Publishing replaces all current files with the ones above.')}
		</div>
	{/if}

	<div class="flex items-center gap-2.5">
		{#if htmlNames.length > 1}
			<span class="text-[12.5px] text-[var(--st-muted)]">{$i18n.t('Opens with')}</span>
			<select
				class="rounded-[7px] border border-[var(--st-border)] bg-transparent px-2.5 py-1 font-mono text-[12.5px]"
				aria-label={$i18n.t('Opens with')}
				bind:value={entryFile}
			>
				{#each htmlNames as n (n)}
					<option value={n}>{n}</option>
				{/each}
			</select>
		{/if}
		<button
			type="button"
			class="st-btn st-btn-primary ml-auto disabled:opacity-50"
			disabled={saving || !dirty}
			onclick={publish}
			>{saving ? $i18n.t('Saving...') : $i18n.t('Publish changes')}</button
		>
	</div>
</div>
```

- [ ] **Step 2: Verify compile**

Run: `npm run check`
Expected: no NEW errors vs baseline.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/sites/tabs/FilesTab.svelte
git commit -m "feat(sites): Files tab with replace-and-publish flow"
```

---

### Task 7: `tabs/SettingsTab.svelte`

**Files:**
- Create: `src/lib/components/sites/tabs/SettingsTab.svelte`

**Interfaces:**
- Consumes: `VisibilityPicker.svelte` (Task 3), `grantsForLevel` from `../lib/form`, `siteAccessLevel` / `isEveryoneGrant` from `../lib/access`, `updateSite` / `updateSiteAccess` from `$lib/apis/sites`.
- Produces props: `{ site: any, onSaved: () => void, onDelete: () => void }`. `onDelete` only requests deletion — the page owns the ConfirmDialog.

- [ ] **Step 1: Write the component**

```svelte
<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { updateSite, updateSiteAccess } from '$lib/apis/sites';
	import VisibilityPicker from '../VisibilityPicker.svelte';
	import { grantsForLevel } from '../lib/form';
	import { isEveryoneGrant, siteAccessLevel } from '../lib/access';

	const i18n = getContext('i18n');

	let { site, onSaved = () => {}, onDelete = () => {} } = $props();

	let name = $state('');
	let slug = $state('');
	let level = $state('private');
	let accessGrants = $state<any[]>([]);
	let saving = $state(false);

	$effect(() => {
		site.id;
		name = site.name ?? '';
		slug = site.slug ?? '';
		level = siteAccessLevel(site);
		accessGrants = (site.access_grants ?? []).filter((g: any) => !isEveryoneGrant(g));
	});

	const save = async () => {
		saving = true;
		try {
			const fd = new FormData();
			fd.append('name', name);
			fd.append('slug', slug);
			await updateSite(localStorage.token, site.id, fd);
			try {
				await updateSiteAccess(localStorage.token, site.id, {
					public: level === 'public',
					access_grants: grantsForLevel(level, accessGrants)
				});
			} catch (err) {
				// The name/slug call above already committed — say so, instead of a
				// generic error implying nothing was saved.
				toast.error(
					$i18n.t('Site files saved, but updating who can view failed: {{error}}', {
						error: `${err}`
					})
				);
				onSaved();
				return;
			}
			toast.success($i18n.t('Site saved'));
			onSaved();
		} catch (err) {
			toast.error(`${err}`);
		} finally {
			saving = false;
		}
	};
</script>

<div class="st-pane flex flex-col">
	<div class="mb-4 flex max-w-md flex-col gap-1">
		<label class="text-xs font-semibold text-[var(--st-muted)]" for="st-name"
			>{$i18n.t('Name')}</label
		>
		<input
			id="st-name"
			class="rounded-[9px] border border-[var(--st-border)] bg-transparent px-2.5 py-2 text-[13.5px] outline-none focus:border-[var(--st-accent)]"
			bind:value={name}
		/>
	</div>
	<div class="mb-4 flex max-w-md flex-col gap-1">
		<label class="text-xs font-semibold text-[var(--st-muted)]" for="st-slug"
			>{$i18n.t('Link')}</label
		>
		<div class="flex items-center gap-1 text-sm">
			<span class="shrink-0 font-mono text-[12.5px] text-[var(--st-faint)]"
				>{window.location.origin}/sites/</span
			>
			<input
				id="st-slug"
				class="min-w-0 flex-1 rounded-[9px] border border-[var(--st-border)] bg-transparent px-2.5 py-2 font-mono text-[12.5px] outline-none focus:border-[var(--st-accent)]"
				bind:value={slug}
			/>
		</div>
	</div>

	<div class="mb-2 text-xs font-semibold text-[var(--st-muted)]">{$i18n.t('Who can view')}</div>
	<VisibilityPicker bind:level bind:accessGrants />

	<div class="mt-4">
		<button
			type="button"
			class="st-btn st-btn-primary disabled:opacity-50"
			disabled={saving || !name.trim() || !slug}
			onclick={save}>{saving ? $i18n.t('Saving...') : $i18n.t('Save changes')}</button
		>
	</div>

	<div
		class="mt-6 max-w-md rounded-xl border border-[color-mix(in_oklab,var(--st-danger)_30%,transparent)] px-4 py-3.5"
	>
		<h4 class="mb-1 text-[13px] font-semibold text-[var(--st-danger)]">
			{$i18n.t('Delete this site')}
		</h4>
		<p class="mb-2.5 text-[12.5px] text-[var(--st-muted)]">
			{$i18n.t('The link will stop working immediately. This cannot be undone.')}
		</p>
		<button type="button" class="st-btn st-btn-danger" onclick={onDelete}
			>{$i18n.t('Delete site...')}</button
		>
	</div>
</div>
```

- [ ] **Step 2: Verify compile**

Run: `npm run check`
Expected: no NEW errors vs baseline.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/sites/tabs/SettingsTab.svelte
git commit -m "feat(sites): Settings tab with access + danger zone"
```

---

### Task 8: Preview tabs (`AnalyticsTab`, `VersionsTab`)

**Files:**
- Create: `src/lib/components/sites/tabs/AnalyticsTab.svelte`
- Create: `src/lib/components/sites/tabs/VersionsTab.svelte`

**Interfaces:**
- Produces props: both take `{}` (no props). Static sample content only, no API calls. Every pane carries the caption `Sample data — this ships in a later phase.`

- [ ] **Step 1: Write `AnalyticsTab.svelte`**

```svelte
<script lang="ts">
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	const data = [
		12, 18, 15, 22, 30, 26, 34, 41, 38, 52, 47, 63, 58, 71, 66, 80, 74, 92, 88, 105, 98, 120,
		112, 131, 124, 140, 133, 151, 146, 162
	];
	const W = 560;
	const H = 120;
	const mx = Math.max(...data);
	const pts = data.map(
		(v, i) =>
			[(i / (data.length - 1)) * W, H - 8 - (v / mx) * (H - 20)] as [number, number]
	);
	const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
	const last = pts[pts.length - 1];

	const topPages: [string, string, number][] = [
		['index.html', '1,904', 100],
		['policies.html', '712', 37],
		['cover.png', '231', 12]
	];
</script>

<div class="st-pane flex flex-col gap-3.5">
	<div class="rounded-xl border border-[var(--st-hairline)] p-4">
		<h4 class="text-[13px] font-semibold">{$i18n.t('Views · last 30 days')}</h4>
		<div class="mb-2.5 text-xs text-[var(--st-faint)]">
			{$i18n.t('Sample data — this ships in a later phase.')}
		</div>
		<svg viewBox="0 0 {W} {H}" class="block h-auto w-full" role="img" aria-label={$i18n.t('Views · last 30 days')}>
			<path d="{line} L{W},{H} L0,{H} Z" fill="var(--st-chart-fill)" />
			<path d={line} fill="none" stroke="var(--st-chart)" stroke-width="2" />
			<circle cx={last[0]} cy={last[1]} r="3.5" fill="var(--st-chart)" />
		</svg>
	</div>

	<div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
		{#each [[$i18n.t('Total views'), '2,847'], [$i18n.t('Unique visitors'), '391'], [$i18n.t('Avg. time on page'), '1:42']] as [k, v] (k)}
			<div class="rounded-xl border border-[var(--st-hairline)] px-3.5 py-3">
				<div class="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--st-faint)]">
					{k}
				</div>
				<div class="mt-0.5 text-[21px] font-bold tabular-nums tracking-tight">{v}</div>
				<div class="text-[11.5px] text-[var(--st-muted)]">{$i18n.t('Sample data')}</div>
			</div>
		{/each}
	</div>

	<div class="rounded-xl border border-[var(--st-hairline)] p-4">
		<h4 class="text-[13px] font-semibold">{$i18n.t('Top pages')}</h4>
		<div class="mb-2.5 text-xs text-[var(--st-faint)]">{$i18n.t('Sample data')}</div>
		<div class="overflow-x-auto">
			<table class="w-full border-collapse text-[13px]">
				<thead>
					<tr>
						<th
							class="border-b border-[var(--st-hairline)] py-1.5 text-left text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--st-faint)]"
							>{$i18n.t('Page')}</th
						>
						<th
							class="w-28 border-b border-[var(--st-hairline)] py-1.5 text-left text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--st-faint)]"
							>{$i18n.t('Views')}</th
						>
						<th class="w-44 border-b border-[var(--st-hairline)]"></th>
					</tr>
				</thead>
				<tbody>
					{#each topPages as [page, views, pct] (page)}
						<tr>
							<td
								class="border-b border-[var(--st-hairline)] py-2 font-mono text-[12.5px] last:border-b-0"
								>/{page}</td
							>
							<td class="border-b border-[var(--st-hairline)] py-2 tabular-nums">{views}</td>
							<td class="border-b border-[var(--st-hairline)] py-2">
								<div class="h-[5px] rounded-[3px] bg-[var(--st-chart)]" style="width: {pct}%"></div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>
</div>
```

- [ ] **Step 2: Write `VersionsTab.svelte`**

```svelte
<script lang="ts">
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	const versions = [
		{
			v: 'v3',
			current: true,
			when: '2 days ago',
			what: 'Replaced 3 files · index.html, charts.css, logo.svg'
		},
		{ v: 'v2', current: false, when: '1 week ago', what: 'Replaced 1 file · index.html' },
		{ v: 'v1', current: false, when: 'Aug 12, 2026', what: 'First publish · 3 files' }
	];
</script>

<div class="st-pane flex flex-col gap-2.5">
	<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-1.5">
		{#each versions as ver (ver.v)}
			<div class="flex gap-3.5 border-b border-[var(--st-hairline)] px-1 py-3.5 last:border-b-0">
				<span
					class="mt-1.5 h-2.5 w-2.5 flex-none rounded-full {ver.current
						? 'bg-[var(--st-live)] ring-4 ring-[var(--st-live-soft)]'
						: 'bg-[var(--st-faint)]'}"
				></span>
				<div class="min-w-0 flex-1">
					<div class="flex items-center gap-2 text-[13.5px] font-semibold">
						{ver.v}
						{#if ver.current}
							<span
								class="rounded-full bg-[var(--st-live-soft)] px-1.5 py-0.5 text-[10px] font-bold tracking-[0.05em] text-[var(--st-live)]"
								>{$i18n.t('CURRENT')}</span
							>
						{/if}
						<span class="text-xs font-normal text-[var(--st-faint)]">· {ver.when}</span>
					</div>
					<div class="text-xs text-[var(--st-muted)]">{ver.what}</div>
				</div>
				{#if !ver.current}
					<button type="button" class="st-btn self-center" disabled title={$i18n.t('Coming soon')}
						>{$i18n.t('Restore')}</button
					>
				{/if}
			</div>
		{/each}
	</div>
	<p class="text-xs text-[var(--st-faint)]">
		{$i18n.t('Sample data — this ships in a later phase.')}
	</p>
</div>
```

- [ ] **Step 3: Verify compile**

Run: `npm run check`
Expected: no NEW errors vs baseline.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/sites/tabs/AnalyticsTab.svelte src/lib/components/sites/tabs/VersionsTab.svelte
git commit -m "feat(sites): Analytics and Versions preview tabs with sample data"
```

---

### Task 9: `CreatePanel.svelte`

**Files:**
- Create: `src/lib/components/sites/CreatePanel.svelte`

**Interfaces:**
- Consumes: `FileDrop`, `VisibilityPicker` (Task 3); `slugify`, `htmlFileNames`, `pickEntryFile`, `mergeFiles`, `grantsForLevel`, `formatSize` from `./lib/form`; `createSite` from `$lib/apis/sites`.
- Produces props: `{ onCancel: () => void, onCreated: (site: any) => void }` — `onCreated` receives the created site object returned by `createSite`.

- [ ] **Step 1: Write the component**

```svelte
<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { createSite } from '$lib/apis/sites';
	import FileDrop from './FileDrop.svelte';
	import VisibilityPicker from './VisibilityPicker.svelte';
	import {
		slugify,
		htmlFileNames,
		pickEntryFile,
		mergeFiles,
		grantsForLevel,
		formatSize
	} from './lib/form';

	const i18n = getContext('i18n');

	let { onCancel = () => {}, onCreated = (_site: any) => {} } = $props();

	let name = $state('');
	let slug = $state('');
	let slugTouched = $state(false);
	let level = $state('private');
	let accessGrants = $state<any[]>([]);
	let files = $state<File[]>([]);
	let entryFile = $state('');
	let saving = $state(false);

	$effect(() => {
		if (!slugTouched) slug = slugify(name);
	});

	const htmlNames = $derived(htmlFileNames(files.map((f) => f.name)));

	$effect(() => {
		entryFile = pickEntryFile(htmlNames, entryFile);
	});

	const submit = async () => {
		saving = true;
		try {
			const fd = new FormData();
			fd.append('name', name);
			fd.append('slug', slug);
			fd.append('public', level === 'public' ? 'true' : 'false');
			fd.append('access_grants', JSON.stringify(grantsForLevel(level, accessGrants)));
			if (entryFile) fd.append('entry_file', entryFile);
			for (const f of files) fd.append('files', f);
			const site = await createSite(localStorage.token, fd);
			toast.success($i18n.t('Site saved'));
			onCreated(site);
		} catch (err) {
			toast.error(`${err}`);
		} finally {
			saving = false;
		}
	};
</script>

<div class="st-pane flex max-w-xl flex-col px-8 py-8 sm:px-10">
	<h3 class="text-lg font-semibold tracking-tight">{$i18n.t('Publish a Site')}</h3>
	<p class="mb-5 text-[13px] text-[var(--st-muted)]">
		{$i18n.t('Upload HTML and assets — get a shareable link in seconds.')}
	</p>

	<div class="mb-4 flex flex-col gap-1">
		<label class="text-xs font-semibold text-[var(--st-muted)]" for="st-new-name"
			>{$i18n.t('Name')}</label
		>
		<input
			id="st-new-name"
			class="rounded-[9px] border border-[var(--st-border)] bg-transparent px-2.5 py-2 text-[13.5px] outline-none focus:border-[var(--st-accent)]"
			bind:value={name}
			placeholder={$i18n.t('My page')}
		/>
	</div>
	<div class="mb-4 flex flex-col gap-1">
		<label class="text-xs font-semibold text-[var(--st-muted)]" for="st-new-slug"
			>{$i18n.t('Link')}</label
		>
		<div class="flex items-center gap-1 text-sm">
			<span class="shrink-0 font-mono text-[12.5px] text-[var(--st-faint)]"
				>{window.location.origin}/sites/</span
			>
			<input
				id="st-new-slug"
				class="min-w-0 flex-1 rounded-[9px] border border-[var(--st-border)] bg-transparent px-2.5 py-2 font-mono text-[12.5px] outline-none focus:border-[var(--st-accent)]"
				bind:value={slug}
				oninput={() => (slugTouched = true)}
			/>
		</div>
	</div>

	<div class="mb-1.5 text-xs font-semibold text-[var(--st-muted)]">{$i18n.t('Files')}</div>
	<FileDrop
		label={$i18n.t('Drop your HTML and asset files here, or click to browse')}
		onFiles={(list) => (files = mergeFiles(files, list))}
	/>
	{#if files.length > 0}
		<div class="mt-1.5 flex flex-col gap-1">
			{#each files as f (f.name)}
				<div class="flex items-center justify-between text-xs text-[var(--st-muted)]">
					<span class="truncate font-mono">{f.name}</span>
					<div class="flex shrink-0 items-center gap-2">
						{#if f.name === entryFile}<span class="st-pv">{$i18n.t('ENTRY')}</span>{/if}
						<span class="tabular-nums text-[var(--st-faint)]">{formatSize(f.size)}</span>
						<button
							type="button"
							class="text-[var(--st-faint)] hover:text-[var(--st-danger)]"
							aria-label={$i18n.t('Remove file')}
							onclick={() => (files = files.filter((x) => x.name !== f.name))}>✕</button
						>
					</div>
				</div>
			{/each}
		</div>
	{/if}
	{#if htmlNames.length > 1}
		<div class="mt-1.5 flex items-center gap-2 text-xs">
			<span class="text-[var(--st-muted)]">{$i18n.t('Opens with')}</span>
			<select
				class="rounded border border-[var(--st-border)] bg-transparent px-2 py-1 font-mono"
				aria-label={$i18n.t('Opens with')}
				bind:value={entryFile}
			>
				{#each htmlNames as n (n)}
					<option value={n}>{n}</option>
				{/each}
			</select>
		</div>
	{/if}

	<div class="mb-1.5 mt-4 text-xs font-semibold text-[var(--st-muted)]">
		{$i18n.t('Who can view')}
	</div>
	<VisibilityPicker bind:level bind:accessGrants />

	<div class="mt-5 flex gap-2">
		<button type="button" class="st-btn" disabled={saving} onclick={onCancel}
			>{$i18n.t('Cancel')}</button
		>
		<button
			type="button"
			class="st-btn st-btn-primary disabled:opacity-50"
			disabled={saving || !name.trim() || !slug || files.length === 0}
			onclick={submit}>{saving ? $i18n.t('Saving...') : $i18n.t('Publish')}</button
		>
	</div>
</div>
```

- [ ] **Step 2: Verify compile**

Run: `npm run check`
Expected: no NEW errors vs baseline.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/sites/CreatePanel.svelte
git commit -m "feat(sites): inline CreatePanel replacing modal create"
```

---

### Task 10: `SiteDetail.svelte` (header + tab bar + panes)

**Files:**
- Create: `src/lib/components/sites/SiteDetail.svelte`

**Interfaces:**
- Consumes: all five tab components (Tasks 5–8), `copyToClipboard` from `$lib/utils`, `siteAccessLevel` from `./lib/access`.
- Produces props: `{ site: any, tab: string ($bindable), onSaved: () => void, onDelete: () => void }`. Tab values: `'overview' | 'files' | 'settings' | 'analytics' | 'versions'`.

- [ ] **Step 1: Write the component**

```svelte
<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { copyToClipboard } from '$lib/utils';
	import { siteAccessLevel } from './lib/access';
	import OverviewTab from './tabs/OverviewTab.svelte';
	import FilesTab from './tabs/FilesTab.svelte';
	import SettingsTab from './tabs/SettingsTab.svelte';
	import AnalyticsTab from './tabs/AnalyticsTab.svelte';
	import VersionsTab from './tabs/VersionsTab.svelte';

	const i18n = getContext('i18n');

	let { site, tab = $bindable('overview'), onSaved = () => {}, onDelete = () => {} } = $props();

	const url = $derived(`${window.location.origin}/sites/${site.slug}/`);
	const isPrivate = $derived(siteAccessLevel(site) === 'private');

	const tabs = $derived([
		{ id: 'overview', label: $i18n.t('Overview'), preview: false },
		{ id: 'files', label: $i18n.t('Files'), preview: false },
		{ id: 'settings', label: $i18n.t('Settings'), preview: false },
		{ id: 'analytics', label: $i18n.t('Analytics'), preview: true },
		{ id: 'versions', label: $i18n.t('Versions'), preview: true }
	]);

	let copied = $state(false);
	const copy = async () => {
		await copyToClipboard(url);
		copied = true;
		setTimeout(() => (copied = false), 1200);
		toast.success($i18n.t('Link copied'));
	};
</script>

<section class="flex min-w-0 flex-col">
	<div class="flex flex-col gap-2.5 px-6 pt-5">
		<div class="flex flex-wrap items-start gap-3.5">
			<div class="min-w-0 flex-1">
				<h2 class="text-xl font-bold tracking-tight text-[var(--st-deep)]">{site.name}</h2>
				<div class="flex items-center gap-2 font-mono text-[12.5px]">
					<a
						class="truncate border-b border-dotted border-[var(--st-faint)] text-[var(--st-muted)] hover:text-[var(--st-accent)]"
						href={url}
						target="_blank"
						rel="noopener">{url}</a
					>
					<button
						type="button"
						class="st-press shrink-0 rounded-[7px] px-2 py-0.5 text-xs text-[var(--st-muted)] hover:bg-[var(--st-hover)] hover:text-[var(--st-ink)]"
						onclick={copy}>{copied ? $i18n.t('Copied ✓') : `⧉ ${$i18n.t('Copy')}`}</button
					>
				</div>
			</div>
			<div class="flex items-center gap-2">
				<span class="st-status">
					<span class="st-dot {isPrivate ? 'st-dot-off' : ''}"></span>
					{isPrivate ? $i18n.t('Private') : $i18n.t('Live')}
				</span>
				<a class="st-btn st-press inline-flex items-center" href={url} target="_blank" rel="noopener"
					>{$i18n.t('Open')} ↗</a
				>
			</div>
		</div>
	</div>

	<div class="flex gap-0.5 overflow-x-auto border-b border-[var(--st-hairline)] px-6 pt-3.5" role="tablist">
		{#each tabs as t (t.id)}
			<button
				type="button"
				role="tab"
				aria-selected={tab === t.id}
				class="relative flex items-center gap-1.5 whitespace-nowrap rounded-t-lg px-3 pb-2.5 pt-2 text-[13px] transition-colors duration-150
					{tab === t.id
					? 'font-semibold text-[var(--st-ink)] after:absolute after:inset-x-2.5 after:-bottom-px after:h-0.5 after:rounded after:bg-[var(--st-accent)] after:content-[\'\']'
					: 'font-medium text-[var(--st-muted)] hover:text-[var(--st-ink)]'}"
				onclick={() => (tab = t.id)}
			>
				{t.label}
				{#if t.preview}<span class="st-pv">{$i18n.t('PREVIEW')}</span>{/if}
			</button>
		{/each}
	</div>

	<div class="flex-1 overflow-y-auto px-6 pb-7 pt-5">
		{#if tab === 'overview'}
			<OverviewTab {site} onGoTab={(t) => (tab = t)} />
		{:else if tab === 'files'}
			<FilesTab {site} {onSaved} />
		{:else if tab === 'settings'}
			<SettingsTab {site} {onSaved} {onDelete} />
		{:else if tab === 'analytics'}
			<AnalyticsTab />
		{:else if tab === 'versions'}
			<VersionsTab />
		{/if}
	</div>
</section>
```

- [ ] **Step 2: Verify compile**

Run: `npm run check`
Expected: no NEW errors vs baseline.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/sites/SiteDetail.svelte
git commit -m "feat(sites): SiteDetail header and tab shell"
```

---

### Task 11: Rewrite `SitesPage.svelte`, delete `SiteEditor.svelte`, full verification

**Files:**
- Modify (full rewrite): `src/lib/components/sites/SitesPage.svelte`
- Delete: `src/lib/components/sites/SiteEditor.svelte`

**Interfaces:**
- Consumes: `SiteRail` (Task 4), `SiteDetail` (Task 10), `CreatePanel` (Task 9), `nextSelection` (Task 2), `getSites` / `deleteSite` from `$lib/apis/sites`, `ConfirmDialog` from `$lib/components/common/ConfirmDialog.svelte`, `sites.css`.
- Produces: the `/sites` route page body (route files `src/routes/(app)/sites/+page.svelte` and `+layout.svelte` are untouched — they already render `SitesPage`).

- [ ] **Step 1: Rewrite `SitesPage.svelte`**

```svelte
<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { user } from '$lib/stores';
	import { getSites, deleteSite } from '$lib/apis/sites';
	import { nextSelection } from './lib/selection';
	import SiteRail from './SiteRail.svelte';
	import SiteDetail from './SiteDetail.svelte';
	import CreatePanel from './CreatePanel.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import './sites.css';

	const i18n = getContext('i18n');

	let sites = $state<any[]>([]);
	let loaded = $state(false);
	let selectedId = $state<string | null>(null);
	let tab = $state('overview');
	let creating = $state(false);
	let showAll = $state(false);
	let showDeleteConfirm = $state(false);

	const selected = $derived(sites.find((s) => s.id === selectedId) ?? null);

	const load = async () => {
		try {
			sites = (await getSites(localStorage.token, showAll)) ?? [];
		} catch (err) {
			toast.error(`${err}`);
		}
		if (selectedId === null || !sites.some((s) => s.id === selectedId)) {
			selectedId = sites[0]?.id ?? null;
			tab = 'overview';
		}
		loaded = true;
	};

	const select = (id: string) => {
		creating = false;
		if (id !== selectedId) {
			selectedId = id;
			tab = 'overview';
		}
	};

	const remove = async () => {
		if (!selected) return;
		try {
			const next = nextSelection(sites, selected.id);
			await deleteSite(localStorage.token, selected.id);
			toast.success($i18n.t('Site deleted'));
			selectedId = next;
			tab = 'overview';
			await load();
		} catch (err) {
			toast.error(`${err}`);
		}
	};

	onMount(load);
</script>

<div class="sites-root mx-auto w-full max-w-[1160px] px-4 py-7 pb-10">
	<div class="mx-1 mb-4 flex flex-wrap items-baseline gap-3">
		<h1 class="text-[22px] font-bold tracking-tight">{$i18n.t('Sites')}</h1>
		<span class="text-[13px] text-[var(--st-muted)]"
			>{$i18n.t('Publish static pages and share them with a link.')}</span
		>
	</div>

	<div
		class="grid min-h-[640px] grid-cols-1 overflow-hidden rounded-2xl border border-[var(--st-border)] bg-[var(--st-card)] shadow-[var(--st-shadow)] md:grid-cols-[280px_1fr]"
	>
		<SiteRail
			{sites}
			{selectedId}
			{creating}
			{showAll}
			isAdmin={$user?.role === 'admin'}
			onSelect={select}
			onCreate={() => (creating = true)}
			onToggleAll={async (v) => {
				showAll = v;
				await load();
			}}
		/>

		{#if creating}
			<CreatePanel
				onCancel={() => (creating = false)}
				onCreated={async (site) => {
					creating = false;
					selectedId = site?.id ?? null;
					tab = 'overview';
					await load();
				}}
			/>
		{:else if selected}
			<SiteDetail site={selected} bind:tab onSaved={load} onDelete={() => (showDeleteConfirm = true)} />
		{:else if loaded}
			<div
				class="flex flex-col items-center justify-center gap-2.5 px-10 py-16 text-center text-[var(--st-muted)]"
			>
				<div class="text-[34px]">🌐</div>
				<div class="text-[15px] font-semibold text-[var(--st-ink)]">
					{$i18n.t('Nothing published yet')}
				</div>
				<div class="max-w-xs text-[13px]">
					{$i18n.t('Upload HTML and assets — get a shareable link in seconds.')}
				</div>
				<button
					type="button"
					class="st-btn st-btn-primary st-press mt-2"
					onclick={() => (creating = true)}>{$i18n.t('Publish a Site')}</button
				>
			</div>
		{/if}
	</div>
</div>

<ConfirmDialog
	bind:show={showDeleteConfirm}
	title={$i18n.t('Delete site?')}
	message={$i18n.t('The link will stop working immediately. This cannot be undone.')}
	on:confirm={remove}
/>
```

- [ ] **Step 2: Delete the modal editor**

```bash
git rm src/lib/components/sites/SiteEditor.svelte
```

Then verify nothing still imports it:
Run: `grep -rn "SiteEditor" src/`
Expected: no matches.

- [ ] **Step 3: Run all sites tests**

Run: `npm run test:frontend -- --run src/lib/components/sites`
Expected: PASS — `form.test.ts`, `selection.test.ts`, plus pre-existing `access.test.ts`, `visibility.test.ts`.

- [ ] **Step 4: Full svelte-check**

Run: `npm run check`
Expected: no NEW errors vs the baseline noted before Task 1.

- [ ] **Step 5: Commit**

```bash
git add -A src/lib/components/sites
git commit -m "feat(sites): two-column workbench UI replacing modal editor"
```

- [ ] **Step 6: Manual browser smoke (deferred to user session — do NOT start a dev server)**

Checklist for the user's own Vite/hot-reload session:
1. `/sites` renders centered shell; rail lists sites with dots/chips/slugs.
2. Select each site — header, URL copy, Live/Private pill correct; tab resets to Overview.
3. Overview stats: file count + size real; Views tile shows PREVIEW pill; quick actions jump tabs.
4. Files: drop files → staged list + ENTRY badge, entry select appears with >1 HTML, Publish changes works, entry-only change enables button.
5. Settings: rename, re-slug, each visibility level round-trips (chip in rail updates), specific shows AccessControl.
6. Delete from danger zone → confirm dialog → next site selected (or empty state).
7. ＋ New site → inline create; Cancel returns; Publish selects the new site.
8. Admin: All users toggle shows owner names; can edit/delete another user's site.
9. Analytics/Versions tabs render sample content with PREVIEW pills; Restore disabled.
10. Dark mode, ~800px width (rail stacks on top), reduced-motion OS setting.
