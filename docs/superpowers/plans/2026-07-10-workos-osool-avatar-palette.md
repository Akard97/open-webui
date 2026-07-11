# WorkOS Osool Avatar Palette Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every initials-based WorkOS user avatar a stable, accessible color from an Osool palette led by `#00313F`.

**Architecture:** Keep label creation on the existing `LABEL_PALETTE`, and add a separate avatar identity contract in `lib/avatar.ts`. That contract hashes a user ID or normalized actor name into an approved background and selects the strongest accessible foreground; every WorkOS avatar renderer consumes the same pair.

**Tech Stack:** Svelte 5, TypeScript, shadcn-svelte Avatar, Vitest, Tailwind CSS 4

## Global Constraints

- Avatar backgrounds are exactly `#00313F`, `#026C80`, `#00A5BA`, `#769A4A`, `#DFA244`, `#C96B5D`, `#54C2D1`, and `#A4C979`.
- `#00313F` is the first palette entry.
- Select the stronger of white and Osool ink `#00313F` when it reaches 4.5:1; use black only when neither brand foreground reaches the threshold.
- Every avatar background/foreground pair must meet WCAG AA's 4.5:1 contrast requirement for normal text.
- The same identity key receives the same pair in light and dark mode.
- `LABEL_PALETTE`, status colors, priorities, health states, sizes, spacing, typography, and membership behavior remain unchanged.
- User-provided content under `docs/mockups/` remains untouched.

---

### Task 1: Add the tested Osool avatar identity contract

**Files:**
- Modify: `src/lib/components/workos/lib/avatar.test.ts`
- Modify: `src/lib/components/workos/lib/avatar.ts`
- Modify: `docs/superpowers/specs/2026-07-10-workos-osool-avatar-palette-design.md`

**Interfaces:**
- Consumes: existing `LABEL_PALETTE` and stable string-hash behavior in `avatar.ts`
- Produces: `AvatarColors`, `AVATAR_BACKGROUNDS`, `AVATAR_PALETTE`, `avatarColors(idOrName: string): AvatarColors`, and the compatibility wrapper `avatarColor(idOrName: string): string`

- [ ] **Step 1: Replace the legacy palette tests with a failing avatar identity contract**

Keep the deterministic and distribution assertions, remove the obsolete assertion that avatar colors come from `LABEL_PALETTE`, and add the following contract to `avatar.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import {
	AVATAR_BACKGROUNDS,
	AVATAR_PALETTE,
	LABEL_PALETTE,
	avatarColor,
	avatarColors
} from './avatar';

const EXPECTED_BACKGROUNDS = [
	'#00313f', '#026c80', '#00a5ba', '#769a4a',
	'#dfa244', '#c96b5d', '#54c2d1', '#a4c979'
];

const BRAND_FOREGROUNDS = ['#ffffff', '#00313f'];

function relativeLuminance(hex: string): number {
	const channels = hex.slice(1).match(/.{2}/g)!.map((part) => parseInt(part, 16) / 255);
	const linear = channels.map((value) =>
		value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
	);
	return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrastRatio(a: string, b: string): number {
	const [lighter, darker] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x);
	return (lighter + 0.05) / (darker + 0.05);
}

describe('avatar identity colors', () => {
	it('uses only the approved Osool backgrounds led by brand ink', () => {
		expect([...AVATAR_BACKGROUNDS]).toEqual(EXPECTED_BACKGROUNDS);
		expect(AVATAR_PALETTE.map((entry) => entry.background)).toEqual(EXPECTED_BACKGROUNDS);
		expect(AVATAR_BACKGROUNDS).not.toEqual(LABEL_PALETTE);
	});

	it('is deterministic and preserves the background compatibility helper', () => {
		expect(avatarColors('user-42')).toEqual(avatarColors('user-42'));
		expect(avatarColor('Ahmad Alsawarieh')).toBe(avatarColors('Ahmad Alsawarieh').background);
	});

	it('spreads different identities across more than one palette entry', () => {
		const colors = new Set(['alice', 'bob', 'carol', 'dave', 'erin', 'frank'].map(avatarColor));
		expect(colors.size).toBeGreaterThan(1);
	});

	it('selects an AA foreground for every approved background', () => {
		for (const { background, foreground } of AVATAR_PALETTE) {
			expect(contrastRatio(background, foreground)).toBeGreaterThanOrEqual(4.5);
			const strongestBrandForeground = BRAND_FOREGROUNDS.reduce((best, candidate) =>
				contrastRatio(background, candidate) > contrastRatio(background, best) ? candidate : best
			);
			const expected = contrastRatio(background, strongestBrandForeground) >= 4.5
				? strongestBrandForeground
				: '#000000';
			expect(foreground).toBe(expected);
		}
	});
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
npm run test:frontend -- src/lib/components/workos/lib/avatar.test.ts --run
```

Expected: FAIL because `AVATAR_BACKGROUNDS`, `AVATAR_PALETTE`, and `avatarColors` are not exported yet.

- [ ] **Step 3: Implement the minimal palette and contrast selection**

Replace `avatar.ts` with the following implementation, preserving the existing label colors exactly:

```ts
export const LABEL_PALETTE = [
	'#00a5ba', '#769a4a', '#d97706', '#dc2626',
	'#7c3aed', '#0ea5e9', '#db2777', '#ca8a04'
];

export const AVATAR_BACKGROUNDS = [
	'#00313f', '#026c80', '#00a5ba', '#769a4a',
	'#dfa244', '#c96b5d', '#54c2d1', '#a4c979'
] as const;

const BRAND_FOREGROUNDS = ['#ffffff', '#00313f'] as const;

export type AvatarColors = Readonly<{ background: string; foreground: string }>;

function hash(value: string): number {
	let result = 0;
	for (let index = 0; index < value.length; index++) {
		result = (result * 31 + value.charCodeAt(index)) | 0;
	}
	return Math.abs(result);
}

function relativeLuminance(hex: string): number {
	const channels = hex.slice(1).match(/.{2}/g)!.map((part) => parseInt(part, 16) / 255);
	const linear = channels.map((value) =>
		value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
	);
	return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrastRatio(a: string, b: string): number {
	const [lighter, darker] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x);
	return (lighter + 0.05) / (darker + 0.05);
}

function foregroundFor(background: string): string {
	const strongestBrandForeground = BRAND_FOREGROUNDS.reduce((best, candidate) =>
		contrastRatio(background, candidate) > contrastRatio(background, best) ? candidate : best
	);
	return contrastRatio(background, strongestBrandForeground) >= 4.5
		? strongestBrandForeground
		: '#000000';
}

export const AVATAR_PALETTE: readonly AvatarColors[] = AVATAR_BACKGROUNDS.map((background) => ({
	background,
	foreground: foregroundFor(background)
}));

export function avatarColors(idOrName: string): AvatarColors {
	return AVATAR_PALETTE[hash(idOrName) % AVATAR_PALETTE.length];
}

export function avatarColor(idOrName: string): string {
	return avatarColors(idOrName).background;
}
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run:

```powershell
npm run test:frontend -- src/lib/components/workos/lib/avatar.test.ts --run
```

Expected: PASS with four tests and no warnings.

- [ ] **Step 5: Review the contract diff**

Run:

```powershell
git diff --check -- src/lib/components/workos/lib/avatar.ts src/lib/components/workos/lib/avatar.test.ts docs/superpowers/specs/2026-07-10-workos-osool-avatar-palette-design.md
```

Expected: exit code 0 and no output.

- [ ] **Step 6: Commit the tested identity contract**

```powershell
git add -- src/lib/components/workos/lib/avatar.ts src/lib/components/workos/lib/avatar.test.ts docs/superpowers/specs/2026-07-10-workos-osool-avatar-palette-design.md
git commit -m "feat(workos): add Osool avatar palette"
```

### Task 2: Apply the identity pair to every WorkOS avatar surface

**Files:**
- Modify: `src/lib/components/workos/views/AssigneeAvatars.svelte`
- Modify: `src/lib/components/workos/views/MyWorkView.svelte`
- Modify: `src/lib/components/workos/chrome/Topbar.svelte`
- Modify: `src/lib/components/workos/chrome/access/TeamSettingsDialog.svelte`
- Modify: `src/lib/components/workos/chrome/access/WorkspaceSettingsDialog.svelte`
- Modify: `src/lib/components/workos/views/timeline/TimelineBar.svelte`

**Interfaces:**
- Consumes: `avatarColors(idOrName: string): AvatarColors` from Task 1
- Produces: consistent inline `background` and `color` values on every initials-based WorkOS user avatar

- [ ] **Step 1: Migrate the shared assignee and My Work fallbacks**

In both files, replace the `avatarColor` import with `avatarColors`. Inside each keyed loop, bind one pair with a Svelte const tag and apply both values:

```svelte
{@const colors = avatarColors(id)}
<AvatarFallback
	class="font-semibold"
	style="background:{colors.background};color:{colors.foreground};font-size:{fontSize}px"
>
	{initials(id)}
</AvatarFallback>
```

For activity and mention rows in `MyWorkView.svelte`, normalize the actor name first, then hash that same value for both the title and color:

```svelte
{@const actorName = cleanName(a.who)}
{@const colors = avatarColors(actorName)}
<Avatar style="width:24px;height:24px" title={actorName}>
	<AvatarFallback
		class="font-semibold"
		style="background:{colors.background};color:{colors.foreground};font-size:10px"
	>
		{initialsOf(actorName)}
	</AvatarFallback>
</Avatar>
```

Use the corresponding normalized value in the mentions loop:

```svelte
{@const actorName = cleanName(m.data?.actor_name ?? '?')}
{@const colors = avatarColors(actorName)}
<Avatar style="width:24px;height:24px" title={actorName}>
	<AvatarFallback
		class="font-semibold"
		style="background:{colors.background};color:{colors.foreground};font-size:10px"
	>
		{initialsOf(actorName)}
	</AvatarFallback>
</Avatar>
```

- [ ] **Step 2: Migrate the top-bar and access-dialog member circles**

Import `avatarColors` from `../lib/avatar` in `Topbar.svelte` and from `../../lib/avatar` in both settings dialogs. Preserve every existing sizing, border, and layout class, remove the fixed `bg-brand-*` and `text-brand-*` classes, and apply the shared pair in the top bar:

```svelte
{@const colors = avatarColors(id)}
<span
	class="size-7 rounded-full border-2 border-white dark:border-gray-950 text-[10px] font-semibold inline-flex items-center justify-center"
	style="background:{colors.background};color:{colors.foreground}"
	title={initials(id)}
>
	{initials(id)}
</span>
```

Use `m.user_id` as the identity key in `TeamSettingsDialog.svelte` and keep its existing `size-9` class:

```svelte
{@const colors = avatarColors(m.user_id)}
<span
	class="size-9 rounded-full text-[11px] font-semibold inline-flex items-center justify-center flex-none"
	style="background:{colors.background};color:{colors.foreground}"
>
	{initials(m.user_id)}
</span>
```

Use the same identity key in `WorkspaceSettingsDialog.svelte` while preserving its `size-7` class:

```svelte
{@const colors = avatarColors(m.user_id)}
<span
	class="size-7 rounded-full text-[11px] font-semibold inline-flex items-center justify-center flex-none"
	style="background:{colors.background};color:{colors.foreground}"
>
	{initials(m.user_id)}
</span>
```

- [ ] **Step 3: Migrate the timeline assignee marker**

Import `avatarColors` from `../../lib/avatar`. Inside the existing assignee block, bind the first assignee's pair and replace the status-colored text/white background:

```svelte
{#if geom.width >= 48 && t.assignee_ids?.length}
	{@const colors = avatarColors(t.assignee_ids[0])}
	<span
		class="ml-auto flex-none size-[18px] rounded-full text-[8px] font-bold inline-flex items-center justify-center"
		style="background:{colors.background};color:{colors.foreground}"
	>
		{initials(t.assignee_ids[0])}
	</span>
{/if}
```

- [ ] **Step 4: Verify no legacy user-avatar colors remain**

Run:

```powershell
rg -n "bg-brand-100 text-brand-700|class=\"text-white font-semibold\"|style=\"color:\{color\}\"" src/lib/components/workos/chrome/Topbar.svelte src/lib/components/workos/chrome/access/TeamSettingsDialog.svelte src/lib/components/workos/chrome/access/WorkspaceSettingsDialog.svelte src/lib/components/workos/views/AssigneeAvatars.svelte src/lib/components/workos/views/MyWorkView.svelte src/lib/components/workos/views/timeline/TimelineBar.svelte
```

Expected: no matches.

Run:

```powershell
rg -l "avatarColors" src/lib/components/workos/chrome/Topbar.svelte src/lib/components/workos/chrome/access/TeamSettingsDialog.svelte src/lib/components/workos/chrome/access/WorkspaceSettingsDialog.svelte src/lib/components/workos/views/AssigneeAvatars.svelte src/lib/components/workos/views/MyWorkView.svelte src/lib/components/workos/views/timeline/TimelineBar.svelte
```

Expected: all six files are listed.

- [ ] **Step 5: Run focused tests and Svelte checking**

Run:

```powershell
npm run test:frontend -- src/lib/components/workos/lib/avatar.test.ts --run
npm run check
```

Expected: the avatar tests pass and `svelte-check` reports zero errors.

- [ ] **Step 6: Inspect the complete implementation diff**

Run:

```powershell
git diff --check
git diff --stat
git status --short
```

Expected: no whitespace errors; only the planned WorkOS implementation, spec correction, plan file, and pre-existing untracked `docs/mockups/` appear.

- [ ] **Step 7: Commit the renderer migration**

```powershell
git add -- src/lib/components/workos/views/AssigneeAvatars.svelte src/lib/components/workos/views/MyWorkView.svelte src/lib/components/workos/chrome/Topbar.svelte src/lib/components/workos/chrome/access/TeamSettingsDialog.svelte src/lib/components/workos/chrome/access/WorkspaceSettingsDialog.svelte src/lib/components/workos/views/timeline/TimelineBar.svelte docs/superpowers/plans/2026-07-10-workos-osool-avatar-palette.md
git commit -m "feat(workos): apply avatar brand colors"
```

### Task 3: Verify the rendered WorkOS surfaces

**Files:**
- Verify only: no source changes expected

**Interfaces:**
- Consumes: the completed avatar identity contract and migrated renderers from Tasks 1 and 2
- Produces: browser evidence that all user-avatar surfaces use stable Osool colors without layout regressions

- [ ] **Step 1: Start or reuse the local frontend**

Run:

```powershell
npm run dev:5050
```

Expected: Vite serves WorkOS on `http://127.0.0.1:5050` without startup errors.

- [ ] **Step 2: Inspect WorkOS in light and dark mode**

Open WorkOS and verify the board, timeline, top-bar stack, My Work activity and mentions, team settings, and restricted-workspace settings. Confirm that:

- the palette is visibly Osool-branded and includes `#00313F`;
- different identity keys receive different deterministic colors;
- initials remain readable on every background;
- overlapping avatars retain visible separation;
- no avatar size, spacing, or interaction changed.

- [ ] **Step 3: Re-run final automated verification**

Run:

```powershell
npm run test:frontend -- src/lib/components/workos/lib/avatar.test.ts --run
npm run check
git status --short
```

Expected: tests and checks pass; `docs/mockups/` remains untracked and untouched; no unexpected files appear.
