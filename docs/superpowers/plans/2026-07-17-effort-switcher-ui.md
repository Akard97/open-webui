# Effort Switcher UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the per-user `EFFORT` valve as a Claude Code-style composer chip + popover slider (Variant B, Osool teal/gold) in the OWUI fork.

**Architecture:** Pure-logic module (`effort.ts`, unit-tested) + one new Svelte component (`EffortMenu.svelte`) mounted in the `MessageInput.svelte` toolbar. Reads/writes the existing valve via `/functions/id/{id}/valves/user*` APIs. No pipe/backend changes.

**Tech Stack:** Svelte 4-style components (`export let`, `$:`), Tailwind, vitest, existing `Dropdown.svelte`/`Tooltip.svelte` primitives, `svelte-sonner` toasts.

**Spec:** `docs/superpowers/specs/2026-07-17-effort-switcher-ui-design.md`

## Global Constraints

- Levels exactly `default` / `xhigh` / `max` (labels: Default / X-High / Max). No low/medium.
- Accents: X-High teal — light text `#17707f`, dark text `#6fc4d4`, base `#3d94a8`; Max gold — light text `#a06716`, dark text `#f0c274`, base `#e0a13f`.
- Detection is generic (user-valves spec has `EFFORT` enum ⊇ the 3 levels) — never hardcode the Osool AI function id.
- Valve writes must MERGE (spread existing user valves, override `EFFORT` only).
- Existing Knobs valves button in MessageInput stays untouched.
- Slider stays LTR in RTL locales (composer row already `dir="ltr"`).
- HARD RULE (user memory): never start a Vite dev server without asking the user first. The user usually runs their own hot-reload server; frontend edits are live on save.
- Never dispatch Svelte edits to a haiku-model subagent (cp1252 corruption risk — user memory).

---

### Task 1: Pure logic module `effort.ts` + unit tests

**Files:**
- Create: `src/lib/components/chat/MessageInput/EffortMenu/effort.ts`
- Test: `src/lib/components/chat/MessageInput/EffortMenu/effort.test.ts`

**Interfaces:**
- Consumes: nothing (pure module).
- Produces (Task 2 imports these exact names):
  - `EFFORT_LEVELS: readonly ['default','xhigh','max']`
  - `type EffortLevel = 'default'|'xhigh'|'max'`
  - `normalizeEffort(value: unknown): EffortLevel`
  - `levelIndex(level: EffortLevel): number`
  - `indexToLevel(index: number): EffortLevel`
  - `functionIdFromModelId(modelId: string): string`
  - `specHasEffort(spec: unknown): boolean`
  - `mergeEffort(valves: unknown, level: EffortLevel): Record<string, unknown>`

- [ ] **Step 1: Write the failing test**

Create `src/lib/components/chat/MessageInput/EffortMenu/effort.test.ts`:

```ts
import { describe, expect, it } from 'vitest';

import {
	EFFORT_LEVELS,
	functionIdFromModelId,
	indexToLevel,
	levelIndex,
	mergeEffort,
	normalizeEffort,
	specHasEffort
} from './effort';

describe('EFFORT_LEVELS', () => {
	it('is exactly default/xhigh/max in order', () => {
		expect([...EFFORT_LEVELS]).toEqual(['default', 'xhigh', 'max']);
	});
});

describe('normalizeEffort', () => {
	it('passes through valid levels', () => {
		expect(normalizeEffort('default')).toBe('default');
		expect(normalizeEffort('xhigh')).toBe('xhigh');
		expect(normalizeEffort('max')).toBe('max');
	});

	it('falls back to default for unknown/missing values', () => {
		expect(normalizeEffort('turbo')).toBe('default');
		expect(normalizeEffort('')).toBe('default');
		expect(normalizeEffort(undefined)).toBe('default');
		expect(normalizeEffort(null)).toBe('default');
		expect(normalizeEffort(3)).toBe('default');
		expect(normalizeEffort({})).toBe('default');
	});
});

describe('levelIndex / indexToLevel', () => {
	it('round-trips all levels', () => {
		for (const level of EFFORT_LEVELS) {
			expect(indexToLevel(levelIndex(level))).toBe(level);
		}
	});

	it('clamps out-of-range indices', () => {
		expect(indexToLevel(-1)).toBe('default');
		expect(indexToLevel(5)).toBe('max');
	});

	it('rounds fractional indices to nearest stop', () => {
		expect(indexToLevel(0.4)).toBe('default');
		expect(indexToLevel(0.6)).toBe('xhigh');
		expect(indexToLevel(1.5)).toBe('max');
	});
});

describe('functionIdFromModelId', () => {
	it('takes the prefix before the first dot', () => {
		expect(functionIdFromModelId('osool_pipe.osool-ai')).toBe('osool_pipe');
	});

	it('returns dotless ids unchanged', () => {
		expect(functionIdFromModelId('osool_pipe')).toBe('osool_pipe');
	});
});

describe('specHasEffort', () => {
	it('accepts a pydantic UserValves spec exposing all three levels', () => {
		const spec = {
			properties: {
				EFFORT: {
					default: 'default',
					description: 'Reasoning effort',
					enum: ['default', 'xhigh', 'max'],
					title: 'Effort',
					type: 'string'
				}
			},
			title: 'UserValves',
			type: 'object'
		};
		expect(specHasEffort(spec)).toBe(true);
	});

	it('accepts extra enum values as long as the three levels are present', () => {
		expect(
			specHasEffort({
				properties: { EFFORT: { enum: ['default', 'xhigh', 'max', 'low'] } }
			})
		).toBe(true);
	});

	it('rejects specs without EFFORT, with partial enums, or garbage input', () => {
		expect(specHasEffort({ properties: {} })).toBe(false);
		expect(specHasEffort({ properties: { EFFORT: { enum: ['default', 'max'] } } })).toBe(false);
		expect(specHasEffort({ properties: { EFFORT: { type: 'string' } } })).toBe(false);
		expect(specHasEffort(null)).toBe(false);
		expect(specHasEffort(undefined)).toBe(false);
		expect(specHasEffort('spec')).toBe(false);
	});
});

describe('mergeEffort', () => {
	it('preserves unrelated valve keys', () => {
		expect(mergeEffort({ EFFORT: 'default', OTHER: 42 }, 'max')).toEqual({
			EFFORT: 'max',
			OTHER: 42
		});
	});

	it('builds a fresh object from null/undefined/array/non-object valves', () => {
		expect(mergeEffort(null, 'xhigh')).toEqual({ EFFORT: 'xhigh' });
		expect(mergeEffort(undefined, 'xhigh')).toEqual({ EFFORT: 'xhigh' });
		expect(mergeEffort([1, 2], 'xhigh')).toEqual({ EFFORT: 'xhigh' });
		expect(mergeEffort('nope', 'xhigh')).toEqual({ EFFORT: 'xhigh' });
	});

	it('does not mutate the input valves object', () => {
		const valves = { EFFORT: 'default' };
		mergeEffort(valves, 'max');
		expect(valves.EFFORT).toBe('default');
	});
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- --run src/lib/components/chat/MessageInput/EffortMenu/effort.test.ts`
Expected: FAIL — cannot resolve `./effort` (module does not exist yet).

- [ ] **Step 3: Write the implementation**

Create `src/lib/components/chat/MessageInput/EffortMenu/effort.ts`:

```ts
export const EFFORT_LEVELS = ['default', 'xhigh', 'max'] as const;
export type EffortLevel = (typeof EFFORT_LEVELS)[number];

export const normalizeEffort = (value: unknown): EffortLevel =>
	EFFORT_LEVELS.includes(value as EffortLevel) ? (value as EffortLevel) : 'default';

export const levelIndex = (level: EffortLevel): number => EFFORT_LEVELS.indexOf(level);

export const indexToLevel = (index: number): EffortLevel =>
	EFFORT_LEVELS[Math.min(EFFORT_LEVELS.length - 1, Math.max(0, Math.round(index)))];

export const functionIdFromModelId = (modelId: string): string => modelId.split('.')[0];

export const specHasEffort = (spec: unknown): boolean => {
	const enumValues = (spec as { properties?: { EFFORT?: { enum?: unknown } } })?.properties
		?.EFFORT?.enum;
	return (
		Array.isArray(enumValues) && EFFORT_LEVELS.every((level) => enumValues.includes(level))
	);
};

export const mergeEffort = (valves: unknown, level: EffortLevel): Record<string, unknown> => ({
	...(valves && typeof valves === 'object' && !Array.isArray(valves)
		? (valves as Record<string, unknown>)
		: {}),
	EFFORT: level
});
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test:frontend -- --run src/lib/components/chat/MessageInput/EffortMenu/effort.test.ts`
Expected: PASS — all tests green.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/chat/MessageInput/EffortMenu/effort.ts src/lib/components/chat/MessageInput/EffortMenu/effort.test.ts
git commit -m "feat(chat): effort level logic for composer effort switcher"
```

---

### Task 2: `EffortMenu.svelte` component

**Files:**
- Create: `src/lib/components/chat/MessageInput/EffortMenu.svelte`

**Interfaces:**
- Consumes: everything from `./EffortMenu/effort` (Task 1 signatures); `getUserValvesById(token, id)`, `getUserValvesSpecById(token, id)`, `updateUserValvesById(token, id, valves)` from `$lib/apis/functions` (all throw on HTTP error); `Dropdown.svelte` (`bind:show`, `side="top"`, slot `content`, trigger = default slot); `Tooltip.svelte` (`content`, `placement`); `Bolt.svelte` icon (`className` prop); `toast` from `svelte-sonner`; i18n context.
- Produces: `<EffortMenu modelId={string | null} />` — renders nothing until spec detection passes (Task 3 mounts it).

- [ ] **Step 1: Write the component**

Create `src/lib/components/chat/MessageInput/EffortMenu.svelte`:

```svelte
<script lang="ts">
	import { getContext, onDestroy, tick } from 'svelte';
	import { toast } from 'svelte-sonner';

	import {
		getUserValvesById,
		getUserValvesSpecById,
		updateUserValvesById
	} from '$lib/apis/functions';

	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Bolt from '$lib/components/icons/Bolt.svelte';

	import {
		EFFORT_LEVELS,
		type EffortLevel,
		functionIdFromModelId,
		indexToLevel,
		levelIndex,
		mergeEffort,
		normalizeEffort,
		specHasEffort
	} from './EffortMenu/effort';

	const i18n = getContext('i18n');

	export let modelId: string | null = null;

	let show = false;
	let available = false;
	let functionId: string | null = null;
	let level: EffortLevel = 'default';
	let confirmedLevel: EffortLevel = 'default';
	let valves: Record<string, unknown> = {};

	let trackEl: HTMLDivElement | null = null;
	let canvasEl: HTMLCanvasElement | null = null;

	let writeTimer: ReturnType<typeof setTimeout> | null = null;
	let initSeq = 0;

	// session cache: function id -> whether its user-valves spec exposes EFFORT
	const specCache: Record<string, boolean> = {};

	const THUMB_POSITIONS = [8, 50, 92];

	$: void init(modelId);

	const init = async (id: string | null) => {
		const seq = ++initSeq;
		show = false;
		available = false;

		if (!id) {
			return;
		}
		const fnId = functionIdFromModelId(id);

		if (!(fnId in specCache)) {
			try {
				const spec = await getUserValvesSpecById(localStorage.token, fnId);
				specCache[fnId] = specHasEffort(spec);
			} catch (e) {
				console.warn('EffortMenu: valves spec fetch failed', e);
				specCache[fnId] = false;
			}
		}
		if (seq !== initSeq || !specCache[fnId]) {
			return;
		}

		let userValves: unknown = {};
		try {
			userValves = await getUserValvesById(localStorage.token, fnId);
		} catch (e) {
			console.warn('EffortMenu: user valves fetch failed', e);
		}
		if (seq !== initSeq) {
			return;
		}

		functionId = fnId;
		valves =
			userValves && typeof userValves === 'object' && !Array.isArray(userValves)
				? (userValves as Record<string, unknown>)
				: {};
		level = normalizeEffort(valves.EFFORT);
		confirmedLevel = level;
		available = true;
	};

	const levelLabel = (l: EffortLevel) =>
		l === 'default' ? $i18n.t('Default') : l === 'xhigh' ? $i18n.t('X-High') : $i18n.t('Max');

	const accentColor = (l: EffortLevel, dark: boolean) =>
		l === 'max' ? (dark ? '#f0c274' : '#e0a13f') : dark ? '#6fc4d4' : '#3d94a8';

	const hexA = (hex: string, alpha: number) => {
		const n = parseInt(hex.slice(1), 16);
		return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
	};

	const drawDots = () => {
		if (!trackEl || !canvasEl) {
			return;
		}
		const w = trackEl.clientWidth;
		const h = trackEl.clientHeight;
		if (w === 0 || h === 0) {
			return;
		}
		const dark = document.documentElement.classList.contains('dark');
		canvasEl.width = w * 2;
		canvasEl.height = h * 2;
		const ctx = canvasEl.getContext('2d');
		if (!ctx) {
			return;
		}
		ctx.scale(2, 2);
		ctx.clearRect(0, 0, w, h);
		const accent = accentColor(level, dark);
		const cols = Math.floor(w / 7);
		const frac = levelIndex(level) / (EFFORT_LEVELS.length - 1);
		for (let c = 0; c < cols; c++) {
			const x = 6 + c * 7;
			const t = cols > 1 ? c / (cols - 1) : 0;
			for (let r = 0; r < 3; r++) {
				const y = h / 2 + (r - 1) * 7;
				const active = t <= frac + 0.001;
				const alpha = active ? (dark ? 0.12 : 0.18) + t * 0.85 : dark ? 0.07 : 0.1;
				const radius = active ? 1.1 + t * 1.3 : 1.1;
				ctx.beginPath();
				ctx.arc(x, y, radius, 0, Math.PI * 2);
				ctx.fillStyle = active
					? hexA(accent, Math.min(1, alpha))
					: dark
						? 'rgba(255,255,255,0.10)'
						: 'rgba(0,0,0,0.10)';
				ctx.fill();
			}
		}
	};

	const scheduleDraw = async () => {
		await tick();
		requestAnimationFrame(drawDots);
	};

	$: if (show) {
		void scheduleDraw();
	}

	const commitWrite = async () => {
		writeTimer = null;
		if (!functionId || level === confirmedLevel) {
			return;
		}
		const target = level;
		try {
			const updated = mergeEffort(valves, target);
			await updateUserValvesById(localStorage.token, functionId, updated);
			valves = updated;
			confirmedLevel = target;
		} catch (e) {
			console.error('EffortMenu: valve update failed', e);
			toast.error($i18n.t('Failed to update effort'));
			level = confirmedLevel;
			void scheduleDraw();
		}
	};

	const setLevel = (next: EffortLevel) => {
		if (next === level) {
			return;
		}
		level = next;
		void scheduleDraw();
		if (writeTimer) {
			clearTimeout(writeTimer);
		}
		writeTimer = setTimeout(() => void commitWrite(), 400);
	};

	const setFromClientX = (clientX: number) => {
		if (!trackEl) {
			return;
		}
		const rect = trackEl.getBoundingClientRect();
		const t = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
		setLevel(indexToLevel(t * (EFFORT_LEVELS.length - 1)));
	};

	const onTrackPointerDown = (e: PointerEvent) => {
		setFromClientX(e.clientX);
		const move = (ev: PointerEvent) => setFromClientX(ev.clientX);
		const up = () => {
			window.removeEventListener('pointermove', move);
			window.removeEventListener('pointerup', up);
		};
		window.addEventListener('pointermove', move);
		window.addEventListener('pointerup', up);
	};

	const onTrackKeydown = (e: KeyboardEvent) => {
		const idx = levelIndex(level);
		if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
			e.preventDefault();
			setLevel(indexToLevel(idx + 1));
		} else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
			e.preventDefault();
			setLevel(indexToLevel(idx - 1));
		} else if (e.key === 'Home') {
			e.preventDefault();
			setLevel('default');
		} else if (e.key === 'End') {
			e.preventDefault();
			setLevel('max');
		}
	};

	onDestroy(() => {
		if (writeTimer) {
			clearTimeout(writeTimer);
			void commitWrite();
		}
	});
</script>

{#if available}
	<Dropdown bind:show side="top" align="start" sideOffset={10}>
		<Tooltip content={$i18n.t('Effort')} placement="top">
			<button
				type="button"
				id="effort-menu-button"
				aria-label={$i18n.t('Effort')}
				class="flex items-center gap-1.5 h-[30px] px-2.5 rounded-full text-xs font-semibold border transition-colors focus:outline-hidden {level ===
				'default'
					? 'border-transparent text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
					: level === 'xhigh'
						? 'text-[#17707f] dark:text-[#6fc4d4] bg-[#3d94a8]/10 dark:bg-[#3d94a8]/15 border-[#3d94a8]/30'
						: 'text-[#a06716] dark:text-[#f0c274] bg-[#e0a13f]/15 dark:bg-[#e0a13f]/10 border-[#e0a13f]/30'}"
			>
				<Bolt className="size-3.5" />
				<span>{level === 'default' ? $i18n.t('Effort') : levelLabel(level)}</span>
			</button>
		</Tooltip>

		<div
			slot="content"
			dir="ltr"
			class="w-[250px] rounded-2xl px-4 pt-3.5 pb-4 bg-white dark:bg-gray-850 border border-gray-100 dark:border-gray-800 shadow-lg"
		>
			<div class="flex items-center gap-1.5 mb-3">
				<span class="text-[13px] font-semibold text-gray-700 dark:text-gray-200"
					>{$i18n.t('Effort')}</span
				>
				<span
					class="text-[13px] font-bold {level === 'max'
						? 'text-[#a06716] dark:text-[#f0c274]'
						: level === 'xhigh'
							? 'text-[#17707f] dark:text-[#6fc4d4]'
							: 'text-gray-500 dark:text-gray-400'}">{levelLabel(level)}</span
				>
				<Tooltip
					content={$i18n.t('Higher effort means deeper reasoning, slower and costlier responses')}
					placement="top"
					className="ml-auto"
				>
					<span
						class="flex items-center justify-center size-4 rounded-full text-[10px] font-bold bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 cursor-default"
						>?</span
					>
				</Tooltip>
			</div>

			<div
				class="flex justify-between text-[11px] font-medium text-gray-400 dark:text-gray-500 mb-2"
			>
				<span>{$i18n.t('Faster')}</span>
				<span>{$i18n.t('Smarter')}</span>
			</div>

			<div
				bind:this={trackEl}
				role="slider"
				tabindex="0"
				aria-label={$i18n.t('Effort')}
				aria-valuemin={0}
				aria-valuemax={EFFORT_LEVELS.length - 1}
				aria-valuenow={levelIndex(level)}
				aria-valuetext={levelLabel(level)}
				class="relative h-[26px] rounded-full bg-gray-100 dark:bg-gray-900 cursor-pointer focus:outline-hidden focus-visible:ring-2 focus-visible:ring-gray-300 dark:focus-visible:ring-gray-700"
				on:pointerdown={onTrackPointerDown}
				on:keydown={onTrackKeydown}
			>
				<div class="absolute inset-0 rounded-full overflow-hidden">
					<canvas bind:this={canvasEl} class="w-full h-full block"></canvas>
				</div>
				<div
					class="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 size-[18px] rounded-full bg-white dark:bg-gray-100 shadow-[0_1px_4px_rgba(0,0,0,0.35)] transition-[left] duration-150 pointer-events-none"
					style="left: {THUMB_POSITIONS[levelIndex(level)]}%"
				></div>
			</div>

			<div class="flex justify-between mt-2 text-[10px] font-semibold uppercase tracking-wide">
				{#each EFFORT_LEVELS as l (l)}
					<button
						type="button"
						class="focus:outline-hidden {l === level
							? 'text-gray-700 dark:text-gray-100'
							: 'text-gray-400 dark:text-gray-600 hover:text-gray-500 dark:hover:text-gray-400'}"
						on:click={() => setLevel(l)}>{levelLabel(l)}</button
					>
				{/each}
			</div>
		</div>
	</Dropdown>
{/if}
```

Notes for the implementer:
- `Dropdown.svelte` wraps the default slot in a trigger that toggles on click — the chip button needs no `on:click`.
- `localStorage.token` is the established auth-token pattern in this codebase.
- `getUserValvesById` returns the instantiated `UserValves` object (e.g. `{ EFFORT: 'default' }`).
- If `Tooltip.svelte` has no `className` prop, wrap the `?` span in a `<span class="ml-auto">` instead — check the component before assuming.

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: completes with no NEW errors relative to the pre-change baseline (run once on a clean tree first if unsure; the repo may carry pre-existing warnings).

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/chat/MessageInput/EffortMenu.svelte
git commit -m "feat(chat): EffortMenu chip + popover slider component"
```

---

### Task 3: Mount in MessageInput + Arabic strings

**Files:**
- Modify: `src/lib/components/chat/MessageInput.svelte` (import block ~line 68; toolbar ~line 1710, between the IntegrationsMenu `{/if}` and the Knobs valves-button `{#if}`)
- Modify: `src/lib/i18n/locales/ar/translation.json`

**Interfaces:**
- Consumes: `<EffortMenu modelId={string | null} />` from Task 2.
- Produces: user-visible chip in the composer toolbar.

- [ ] **Step 1: Import the component**

In `src/lib/components/chat/MessageInput.svelte`, next to the existing line `import InputMenu from './MessageInput/InputMenu.svelte';` (~line 68), add:

```ts
	import EffortMenu from './MessageInput/EffortMenu.svelte';
```

- [ ] **Step 2: Mount in the toolbar**

In the same file, find the block ending the IntegrationsMenu conditional (`</IntegrationsMenu>` followed by `{/if}`, ~line 1709) and the Knobs valves button block that starts `{#if selectedModelIds.length === 1 && $models.find((m) => m.id === selectedModelIds[0])?.has_user_valves}` (~line 1711). Insert BETWEEN them:

```svelte
									{#if selectedModelIds.length === 1 && $models.find((m) => m.id === selectedModelIds[0])?.has_user_valves}
										<EffortMenu modelId={selectedModelIds[0]} />
									{/if}
```

(The component additionally hides itself unless the function's user-valves spec exposes `EFFORT`, so non-Osool pipes with valves just show nothing.)

- [ ] **Step 3: Add Arabic strings**

In `src/lib/i18n/locales/ar/translation.json`, add these keys (alphabetical placement within the file's existing ordering):

```json
	"Effort": "الجهد",
	"Failed to update effort": "فشل تحديث الجهد",
	"Faster": "أسرع",
	"Higher effort means deeper reasoning, slower and costlier responses": "جهد أعلى يعني تفكيرًا أعمق واستجابات أبطأ وأعلى تكلفة",
	"Smarter": "أذكى",
	"X-High": "مرتفع جدًا"
```

Check first whether `"Default"`, `"Max"`, and `"Effort"` already exist in the file (OWUI ships many keys) — only add the missing ones. English needs no changes (i18next falls back to the key).

- [ ] **Step 4: Type-check**

Run: `npm run check`
Expected: no NEW errors.

- [ ] **Step 5: Run the full frontend test suite**

Run: `npm run test:frontend -- --run`
Expected: PASS (all pre-existing suites + Task 1 suite).

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/chat/MessageInput.svelte src/lib/i18n/locales/ar/translation.json
git commit -m "feat(chat): mount effort switcher in composer toolbar"
```

---

### Task 4: Browser smoke (manual, with user's dev server)

**Files:** none (verification only).

**Interfaces:** consumes the running app. HARD RULE: do NOT start a Vite dev server yourself — ask the user which URL to use (they normally run their own hot-reload server; the Docker container serves the built UI on :8080 and does NOT pick up frontend edits).

- [ ] **Step 1: Ask the user for the dev server URL** (usually http://localhost:5173) and confirm the Osool AI pipe (v0.2.3+, with `UserValves.EFFORT`) is installed in the target instance.

- [ ] **Step 2: Smoke checklist** (browser pane, light + dark via theme toggle, and once with Arabic locale for RTL):

- Chip appears only when Osool AI is the single selected model; hidden for other models and multi-model selection.
- Idle chip = muted "⚡ Effort"; X-High → teal chip "X-High"; Max → gold chip "Max". Levels persist after reload (valve read-back works).
- Popover opens above the chip; header level name recolors; dotted track brightens toward Smarter; thumb animates between 3 stops.
- Click track / drag / ArrowLeft-ArrowRight / Home / End all change stops.
- Chat Controls → Valves → Osool AI shows the same EFFORT value after changing via chip (sync through shared valve).
- Rapid flipping produces one write (network tab: single `valves/user/update` after ~400 ms quiet).
- Kill network (devtools offline) → change level → error toast + chip reverts.
- Arabic locale: composer strip stays usable; slider remains LTR.

- [ ] **Step 3: Fix anything found, re-run relevant checks, commit fixes.**

---

## Self-review notes

- Spec coverage: chip states/placement (T2/T3), detection via spec (T1 `specHasEffort` + T2 `init`), merge-on-write (T1 `mergeEffort` + T2 `commitWrite`), debounce+revert+toast (T2), a11y keys + `role="slider"` (T2), LTR-in-RTL (`dir="ltr"` on popover content; composer row already LTR) (T2/T4), i18n ar (T3), no pipe/backend changes (no such task exists), Knobs untouched (T3 inserts a sibling only), testing section (T1 unit tests, T4 smoke).
- Type consistency: `EffortLevel`, `mergeEffort(valves, level)`, `specHasEffort(spec)`, `functionIdFromModelId(modelId)` used identically in T1 and T2. `modelId` prop name matches T2 definition and T3 usage.
