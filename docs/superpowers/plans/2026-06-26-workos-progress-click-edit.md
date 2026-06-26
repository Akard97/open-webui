# WorkOS Click-to-edit Task Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the WorkOS task-detail "Edit progress" button + range slider with direct interactions — click/drag the progress bar (after an explicit arm step) and click the `%` text to type an exact value.

**Architecture:** Extract the one piece of pure logic (pointer position → percent) into `progress.ts` and unit-test it. Wire all DOM interaction (arm, click, drag, keyboard, percent input) into `TaskDetail.svelte`, reusing the existing `editTask` store function for saves. Frontend-only; no backend/API/store changes.

**Tech Stack:** SvelteKit + TypeScript, Tailwind, Vitest. Pointer Events API for click/drag.

## Global Constraints

- Progress is editable **only when the task has no subtasks**: `(t.subtask_total ?? 0) === 0`. When subtasks exist, the row is non-interactive and shows "X/Y subtasks complete" (unchanged).
- Progress values are integers clamped to `0–100`.
- All saves go through the existing `editTask(id, { progress })` from `src/lib/components/workos/lib/store.ts`. No new save path.
- No backend, `api.ts`, or store changes.
- Match existing file style: tabs for indentation, Svelte 5 event attribute syntax (`onclick`, `onpointerdown`), Tailwind classes consistent with the surrounding code.

---

### Task 1: Pure `pointerToPercent` helper

Adds the only unit-testable logic: convert a pointer X coordinate + the bar's bounding rect into a clamped integer percent.

**Files:**
- Modify: `src/lib/components/workos/lib/progress.ts`
- Test: `src/lib/components/workos/lib/progress.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces: `pointerToPercent(clientX: number, rect: { left: number; width: number }): number` — returns an integer in `[0, 100]`. Used by Task 2.

- [ ] **Step 1: Write the failing tests**

Append to `src/lib/components/workos/lib/progress.test.ts`. Also add `pointerToPercent` to the existing import on line 2 (`import { actualProgress, plannedProgress, taskHealth, pointerToPercent } from './progress';`).

```ts
describe('pointerToPercent', () => {
	const rect = { left: 100, width: 200 }; // spans clientX 100..300

	it('returns 0 at the left edge', () => {
		expect(pointerToPercent(100, rect)).toBe(0);
	});

	it('returns 100 at the right edge', () => {
		expect(pointerToPercent(300, rect)).toBe(100);
	});

	it('returns 50 at the midpoint', () => {
		expect(pointerToPercent(200, rect)).toBe(50);
	});

	it('clamps to 0 left of the bar', () => {
		expect(pointerToPercent(40, rect)).toBe(0);
	});

	it('clamps to 100 right of the bar', () => {
		expect(pointerToPercent(999, rect)).toBe(100);
	});

	it('rounds to the nearest integer', () => {
		expect(pointerToPercent(101, rect)).toBe(1); // 0.5% -> rounds to 1 (Math.round)
		expect(pointerToPercent(102, { left: 0, width: 300 })).toBe(34); // 102/300=0.34
	});

	it('returns 0 for a zero-width rect', () => {
		expect(pointerToPercent(50, { left: 0, width: 0 })).toBe(0);
	});
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test:frontend -- src/lib/components/workos/lib/progress.test.ts`
Expected: FAIL — `pointerToPercent is not a function` / not exported.

- [ ] **Step 3: Write the implementation**

Append to `src/lib/components/workos/lib/progress.ts` (reuses the existing `Math.round` + clamp idiom already in the file):

```ts
export function pointerToPercent(
	clientX: number,
	rect: { left: number; width: number }
): number {
	if (rect.width <= 0) return 0;
	const fraction = (clientX - rect.left) / rect.width;
	return Math.max(0, Math.min(100, Math.round(fraction * 100)));
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test:frontend -- src/lib/components/workos/lib/progress.test.ts`
Expected: PASS (all `pointerToPercent` cases green, existing cases still green).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/progress.ts src/lib/components/workos/lib/progress.test.ts
git commit -m "feat(workos): add pointerToPercent helper for progress bar editing"
```

---

### Task 2: Arm + click/drag the progress bar in TaskDetail

Makes the detail-view progress bar interactive: a first click (or the pencil) arms it; once armed, click or drag sets the value with live feedback and a single save on release; keyboard arrows adjust when armed; click-outside / Escape / Enter disarm.

**Files:**
- Modify: `src/lib/components/workos/views/TaskDetail.svelte` (script block ~lines 39–59; progress markup ~lines 238–286)

**Interfaces:**
- Consumes: `pointerToPercent` (Task 1); existing `editTask`, `actualProgress`, `plannedProgress`, `taskHealth`, `HEALTH_LABEL`.
- Produces: in-component state `barArmed`, `dragValue`, `dragging`, `barEl`, derived `editable` and `barValue` — consumed by Task 3's percent-text path (`editable`, `barValue`).

> This task is DOM/pointer interaction, not unit-testable in Vitest. The test cycle is `npm run check` (type safety) plus a scripted browser smoke. Follow the steps exactly.

- [ ] **Step 1: Add imports and replace progress state**

In `src/lib/components/workos/views/TaskDetail.svelte`, update the progress import on line 10 to add `pointerToPercent`:

```ts
	import { plannedProgress, actualProgress, taskHealth, HEALTH_LABEL, pointerToPercent } from '../lib/progress';
```

Replace the single line `let editingProgress = false;` (line 43) with:

```ts
	let barArmed = false;
	let dragValue: number | null = null;
	let dragging = false;
	let barEl: HTMLDivElement | null = null;
	let lastTaskId: string | null = null;
```

- [ ] **Step 2: Add derived values and handlers**

Immediately after the `actualBarColor` reactive block (after line 59, before the closing `</script>` on line 60), add:

```ts
	$: editable = !!t && (t.subtask_total ?? 0) === 0;
	$: barValue = dragValue ?? actual;

	// Reset interaction state when switching tasks so an armed bar never leaks across tasks.
	$: if (t && t.id !== lastTaskId) {
		lastTaskId = t.id;
		barArmed = false;
		dragging = false;
		dragValue = null;
	}

	function armBar() {
		if (editable) barArmed = true;
	}

	function setProgressFromEvent(e: PointerEvent) {
		if (!barEl) return;
		dragValue = pointerToPercent(e.clientX, barEl.getBoundingClientRect());
	}

	function commitDrag() {
		if (!t || dragValue === null) return;
		const v = dragValue;
		dragValue = null;
		if (v !== t.progress) editTask(t.id, { progress: v });
	}

	function onBarPointerDown(e: PointerEvent) {
		if (!editable) return;
		if (!barArmed) {
			barArmed = true; // first click only arms; does not change the value
			return;
		}
		dragging = true;
		(e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
		setProgressFromEvent(e);
	}

	function onBarPointerMove(e: PointerEvent) {
		if (dragging) setProgressFromEvent(e);
	}

	function onBarPointerUp(e: PointerEvent) {
		if (!dragging) return;
		dragging = false;
		(e.currentTarget as HTMLElement).releasePointerCapture?.(e.pointerId);
		commitDrag();
	}

	function onBarKeyDown(e: KeyboardEvent) {
		if (!editable || !t) return;
		if (e.key === 'Escape' || e.key === 'Enter') {
			barArmed = false;
			return;
		}
		if (!barArmed) {
			if (e.key === ' ' || e.key === 'Spacebar') {
				e.preventDefault();
				barArmed = true;
			}
			return;
		}
		if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
			e.preventDefault();
			const delta = e.key === 'ArrowRight' ? 1 : -1;
			const next = Math.max(0, Math.min(100, t.progress + delta));
			if (next !== t.progress) editTask(t.id, { progress: next });
		}
	}

	function onWindowPointerDown(e: PointerEvent) {
		if (barArmed && barEl && !barEl.contains(e.target as Node)) barArmed = false;
	}
```

- [ ] **Step 3: Add the window listener for click-outside disarm**

Add this as the first line inside the component's top-level markup. Place it right before the `<Dialog.Root ...>` (or whichever element currently opens the markup, just after `</script>`):

```svelte
<svelte:window onpointerdown={onWindowPointerDown} />
```

- [ ] **Step 4: Replace the bar markup**

Replace the bar container block (lines 242–247):

```svelte
									<div class="relative flex-1 h-2.5 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
										{#if planned !== null}
											<div class="absolute inset-y-0 left-0 bg-gray-300 dark:bg-gray-600 rounded-full" style="width:{planned}%"></div>
										{/if}
										<div class="absolute left-0 top-1/2 -translate-y-1/2 h-1 {actualBarColor} rounded-full" style="width:{actual}%"></div>
									</div>
```

with:

```svelte
									<div
										bind:this={barEl}
										role={editable ? 'slider' : undefined}
										aria-valuenow={editable ? barValue : undefined}
										aria-valuemin={editable ? 0 : undefined}
										aria-valuemax={editable ? 100 : undefined}
										tabindex={editable ? 0 : undefined}
										class="relative flex-1 h-2.5 rounded-full bg-gray-100 dark:bg-gray-800 {barArmed ? 'overflow-visible ring-2 ring-primary/40' : 'overflow-hidden'} {editable ? 'cursor-pointer touch-none select-none' : ''}"
										onpointerdown={editable ? onBarPointerDown : undefined}
										onpointermove={editable ? onBarPointerMove : undefined}
										onpointerup={editable ? onBarPointerUp : undefined}
										onkeydown={editable ? onBarKeyDown : undefined}
									>
										{#if planned !== null}
											<div class="absolute inset-y-0 left-0 bg-gray-300 dark:bg-gray-600 rounded-full" style="width:{planned}%"></div>
										{/if}
										<div class="absolute left-0 top-1/2 -translate-y-1/2 h-1 {actualBarColor} rounded-full" style="width:{barValue}%"></div>
										{#if barArmed}
											<div class="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-white border-2 border-primary shadow" style="left:{barValue}%"></div>
										{/if}
									</div>
```

- [ ] **Step 5: Update the legend to track the live value**

In the legend block, change `Actual {actual}%` (line 253) to use the live value so the number moves during a drag:

```svelte
											<span class="inline-block w-2.5 h-1 rounded-full {actualBarColor}"></span>Actual {barValue}%
```

- [ ] **Step 6: Replace the edit block (button + slider) with the pencil affordance**

Replace the entire `{#if (t.subtask_total ?? 0) === 0 && editingProgress} … {/if}` block (lines 265–284) with:

```svelte
									{#if (t.subtask_total ?? 0) === 0}
										{#if barArmed}
											<div class="text-xs text-gray-400">Click or drag the bar to set progress. Press Esc or Enter when done.</div>
										{:else}
											<button
												type="button"
												class="inline-flex items-center gap-1.5 text-xs font-medium text-primary rounded-md border border-brand-200 dark:border-brand-800 px-2 py-1 cursor-pointer transition-colors hover:bg-accent"
												onclick={armBar}
											>
												<Icon name="pencil" size={12} />
												Edit progress
											</button>
										{/if}
									{:else}
										<div class="text-xs text-gray-400">{t.subtask_completed ?? 0}/{t.subtask_total ?? 0} subtasks complete</div>
									{/if}
```

- [ ] **Step 7: Type-check**

Run: `npm run check`
Expected: PASS — no new errors referencing `TaskDetail.svelte` (no `editingProgress` undefined, no type errors on the new handlers).

- [ ] **Step 8: Browser smoke (WorkOS detail view)**

Start the app preview, open WorkOS, open an `in_progress` task **with no subtasks**, and verify:
1. The bar shows the pencil "Edit progress" affordance and is not draggable before arming.
2. Click the bar once → handle appears, value unchanged, hint text shows.
3. Click elsewhere on the armed bar → value jumps to that position; the `%` number and legend update; one save occurs (task persists after reload).
4. Drag along the armed bar → value scrubs live; on release it saves once.
5. With the bar focused and armed, press `←`/`→` → value changes by 1 and saves.
6. Press `Escape` (or click outside) → handle disappears, value retained.
7. Open a task **with subtasks** → bar is not interactive, "X/Y subtasks complete" shows, no pencil.

Capture a screenshot of the armed bar as proof.

- [ ] **Step 9: Commit**

```bash
git add src/lib/components/workos/views/TaskDetail.svelte
git commit -m "feat(workos): arm and click/drag the task progress bar to edit progress"
```

---

### Task 3: Click the percentage text to type a value

Turns the `%` number into a parallel quick path: click it → focused number input; Enter/blur commits (clamped); Escape cancels; empty/invalid reverts. Available whenever progress is editable, independent of the bar's armed state.

**Files:**
- Modify: `src/lib/components/workos/views/TaskDetail.svelte` (script block; `%` text markup ~line 248)

**Interfaces:**
- Consumes: `editable` and `barValue` (Task 2), existing `editTask`.
- Produces: nothing consumed downstream.

> DOM interaction — verified via `npm run check` plus browser smoke.

- [ ] **Step 1: Add percent-edit state and handlers**

In the script block, add to the state declarations (next to the Task 2 state added after line 43):

```ts
	let editingPercent = false;
	let percentDraft = '';
	let suppressPercentCommit = false;
```

Add the `t.id` reset so percent editing also clears on task switch — extend the existing reset reactive from Task 2:

```ts
	$: if (t && t.id !== lastTaskId) {
		lastTaskId = t.id;
		barArmed = false;
		dragging = false;
		dragValue = null;
		editingPercent = false;
	}
```

Add the handlers after the bar handlers:

```ts
	function focusSelect(node: HTMLInputElement) {
		node.focus();
		node.select();
	}

	function startPercentEdit() {
		if (!editable || !t) return;
		percentDraft = String(t.progress);
		suppressPercentCommit = false;
		editingPercent = true;
	}

	function commitPercent() {
		if (suppressPercentCommit) {
			suppressPercentCommit = false;
			return;
		}
		if (!t) {
			editingPercent = false;
			return;
		}
		const trimmed = percentDraft.trim();
		const n = Number(trimmed);
		editingPercent = false;
		if (trimmed === '' || Number.isNaN(n)) return; // revert, no save
		const v = Math.max(0, Math.min(100, Math.round(n)));
		if (v !== t.progress) editTask(t.id, { progress: v });
	}

	function cancelPercent() {
		suppressPercentCommit = true; // stop the blur that follows from saving
		editingPercent = false;
	}

	function onPercentKey(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			commitPercent();
		} else if (e.key === 'Escape') {
			e.preventDefault();
			cancelPercent();
		}
	}
```

- [ ] **Step 2: Replace the `%` text with a clickable input**

Replace the percent span (line 248):

```svelte
										<span class="text-sm text-gray-500 w-10 text-right">{actual}%</span>
```

with:

```svelte
										{#if editingPercent}
											<input
												type="number"
												min="0"
												max="100"
												class="w-12 text-sm text-right rounded border border-brand-200 dark:border-brand-800 bg-transparent px-1 py-0.5 tabular-nums"
												bind:value={percentDraft}
												use:focusSelect
												onkeydown={onPercentKey}
												onblur={commitPercent}
											/>
										{:else}
											<button
												type="button"
												disabled={!editable}
												class="text-sm text-gray-500 w-10 text-right tabular-nums {editable ? 'cursor-text hover:text-primary' : 'cursor-default'}"
												onclick={startPercentEdit}
											>{barValue}%</button>
										{/if}
```

- [ ] **Step 3: Type-check**

Run: `npm run check`
Expected: PASS — no new errors referencing `TaskDetail.svelte`.

- [ ] **Step 4: Browser smoke (percent input)**

On an `in_progress` task with no subtasks:
1. Click the `%` number → it becomes a focused, selected input pre-filled with the current value.
2. Type `73`, press `Enter` → bar fill and number update to 73%; persists after reload.
3. Click the number, type `150`, blur → clamps to 100%.
4. Click the number, change it, press `Escape` → reverts to previous value, no save (verify via reload).
5. Click the number, clear it, blur → reverts, no save.
6. On a task **with subtasks** → the number is not clickable (disabled), no input appears.

Capture a screenshot of the active number input as proof.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/views/TaskDetail.svelte
git commit -m "feat(workos): click the progress percentage to type an exact value"
```

---

## Self-Review

**Spec coverage:**
- Detail-view-only scope → Tasks 2–3 touch only `TaskDetail.svelte`. ✓
- Editable only when no subtasks → `editable` guard gates bar handlers, pencil, and percent input; subtask branch unchanged. ✓
- Bar arm-first, then click/drag → `onBarPointerDown` arms on first click (early return), sets on subsequent interactions; `commitDrag` saves once on release. ✓
- Both arm methods (bar click + pencil) → `onBarPointerDown` and `armBar`. ✓
- Exit on outside-click / Escape / Enter → `onWindowPointerDown`, `onBarKeyDown`. ✓
- Live-during-drag, save-on-release → `dragValue` drives `barValue` (bar fill + legend + number); `editTask` only in `commitDrag`/keyboard. ✓
- Exact integers 0–100 → `pointerToPercent` rounds + clamps; keyboard and percent commit clamp. ✓
- Percent text click→type, Enter/blur commit, Escape cancel, invalid reverts → Task 3 handlers, `suppressPercentCommit` resolves the Escape→blur race. ✓
- Available whenever editable, independent of armed state → percent button gated only by `editable`. ✓
- Accessibility: `role="slider"`, `aria-valuenow/min/max`, focusable, arrow keys → Task 2 Step 4 + `onBarKeyDown`. ✓
- Unchanged save path / no backend changes → only `editTask` used. ✓

**Placeholder scan:** No TBD/TODO; all code shown in full; test code complete. ✓

**Type consistency:** `pointerToPercent(clientX, rect)` signature identical in Task 1 (defined) and Task 2 (used). `editable`/`barValue`/`dragValue` names consistent across Tasks 2–3. The Task-3 reset reactive supersedes the Task-2 version (same block, one extra line) — implementers applying Task 3 edit the block from Task 2 rather than adding a second one. ✓
