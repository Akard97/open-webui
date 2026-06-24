# WorkOS Task Detail Panel Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the WorkOS task detail drawer to match the reference image (clean, read-first layout with avatars, tabs, and attachment cards) using shadcn-svelte primitives and the Osool teal accent.

**Architecture:** Rewrite `views/TaskDetail.svelte` as a thin composition shell over small focused subcomponents under `views/detail/`. All editing reuses existing store actions (`editTask`, `removeTask`, `uploadFiles`, `removeAttachment`) — no backend or store changes. Fields render as display values and reveal an inline editor / shadcn `DropdownMenu` on click. The combined feed splits into `Comments` and `Activities` tabs plus a `Subtasks` placeholder.

**Tech Stack:** Svelte 5 (WorkOS components use legacy `export let` / `$:` reactivity with new `onclick` event syntax — match that style), shadcn-svelte (`bits-ui` ^2.18.1) primitives in `src/lib/components/ui/`, Tailwind, Vitest.

## Global Constraints

- **Accent color:** Osool **teal** — `teal-600` (light) / `teal-400`–`teal-500` (dark) for links, progress fill, focus/hover affordances, avatar fallback tint. Never introduce the reference image's indigo/purple. Status/priority/label semantic colors stay as defined in `Pills.svelte` / `StatusDot.svelte`.
- **Scope to WorkOS only:** all new markup lives inside `.workos-root`. Do not touch global styles or other routes.
- **shadcn imports:** import from `$lib/components/ui/<name>` (e.g. `import * as DropdownMenu from '$lib/components/ui/dropdown-menu';`). The semantic tokens (`--popover`, `--border`, `--radius`) are global so bits-ui portalled overlays stay themed.
- **Dark mode:** every new surface must carry `dark:` variants.
- **Per-task gate for `.svelte` files:** `npm run check` must report **no new errors** in the files you touched (the command scans the whole repo; pre-existing unrelated errors are out of scope — compare against the file you changed). For `.ts` logic: `npm run test:frontend`.
- **Single assignee** (model has one `assignee_id`); **no** multi-assignee or invite flow.
- **Subtasks** are a placeholder only — no data model or CRUD.

---

### Task 1: Long date formatter

Adds the "5 March 2024" formatter used by the Due date row. Pure logic → TDD.

**Files:**
- Modify: `src/lib/components/workos/lib/format.ts`
- Test: `src/lib/components/workos/lib/format.test.ts`

**Interfaces:**
- Produces: `formatDateLong(ts: number): string` → day-month-year, e.g. `"5 March 2024"`.

- [ ] **Step 1: Write the failing test**

Append to `src/lib/components/workos/lib/format.test.ts`:

```ts
import { formatDateLong } from './format';

describe('formatDateLong', () => {
	it('renders day month year', () => {
		const ts = new Date(2024, 2, 5).getTime(); // 5 March 2024, local
		expect(formatDateLong(ts)).toBe('5 March 2024');
	});
	it('renders a single-digit day without padding', () => {
		const ts = new Date(2024, 11, 9).getTime(); // 9 December 2024
		expect(formatDateLong(ts)).toBe('9 December 2024');
	});
});
```

Also add `formatDateLong` to the existing top import:

```ts
import { formatDueDate, isOverdue } from './format';
```
becomes
```ts
import { formatDueDate, isOverdue, formatDateLong } from './format';
```
(Then delete the separate `import { formatDateLong }` line you added above so there's one import — or keep a single combined import; do not import the symbol twice.)

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/lib/components/workos/lib/format.test.ts`
Expected: FAIL — `formatDateLong is not a function` / not exported.

- [ ] **Step 3: Write minimal implementation**

Append to `src/lib/components/workos/lib/format.ts`:

```ts
/** "5 March 2024" — long day-month-year (en-GB gives day-first ordering). */
export function formatDateLong(ts: number): string {
	return new Date(ts).toLocaleDateString('en-GB', {
		day: 'numeric',
		month: 'long',
		year: 'numeric'
	});
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test:frontend -- src/lib/components/workos/lib/format.test.ts`
Expected: PASS (all `format` tests green).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/format.ts src/lib/components/workos/lib/format.test.ts
git commit -m "feat(workos): add formatDateLong helper for task detail due date"
```

---

### Task 2: Add detail-panel icons

The redesign needs a few Lucide glyphs not yet in the icon set.

**Files:**
- Modify: `src/lib/components/workos/ui/Icon.svelte`

**Interfaces:**
- Produces: new `Icon` names available — `maximize`, `circle`, `tag`, `align-left`, `download`, `file`.

- [ ] **Step 1: Add the icon paths**

In `src/lib/components/workos/ui/Icon.svelte`, add these entries to the `LUCIDE` record (place them alongside the existing entries, before the closing `};`):

```ts
		maximize: '<path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/>',
		circle: '<circle cx="12" cy="12" r="10"/>',
		tag: '<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r=".5" fill="currentColor"/>',
		'align-left': '<line x1="21" x2="3" y1="6" y2="6"/><line x1="15" x2="3" y1="12" y2="12"/><line x1="17" x2="3" y1="18" y2="18"/>',
		download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
		file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>'
```

(The last existing entry `zap` ends without a trailing comma — add a comma after it before inserting, and ensure the new block's final `file` entry has no trailing comma.)

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: no new errors in `Icon.svelte`.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/workos/ui/Icon.svelte
git commit -m "feat(workos): add icons for task detail redesign"
```

---

### Task 3: PropertyRow presentational shell

A reusable row: leading icon + label + value slot. Used by every property in the panel.

**Files:**
- Create: `src/lib/components/workos/views/detail/PropertyRow.svelte`

**Interfaces:**
- Produces: `PropertyRow` with props `icon: string`, `label: string`, `align?: 'center' | 'start'` (default `'center'`), default slot for the value/editor.

- [ ] **Step 1: Create the component**

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';

	export let icon: string;
	export let label: string;
	export let align: 'center' | 'start' = 'center';
</script>

<div class="flex gap-3 min-h-9 {align === 'start' ? 'items-start' : 'items-center'}">
	<span
		class="flex items-center gap-2 w-28 flex-none text-sm text-gray-500 dark:text-gray-400 {align === 'start' ? 'pt-1.5' : ''}"
	>
		<Icon name={icon} size={15} />
		{label}
	</span>
	<div class="flex-1 min-w-0 text-sm">
		<slot />
	</div>
</div>
```

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: no new errors in `PropertyRow.svelte`.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/workos/views/detail/PropertyRow.svelte
git commit -m "feat(workos): add PropertyRow shell for task detail"
```

---

### Task 4: Subtasks placeholder

Empty-state shown in the Subtasks tab (real subtasks come later).

**Files:**
- Create: `src/lib/components/workos/views/detail/SubtasksPlaceholder.svelte`

**Interfaces:**
- Produces: `SubtasksPlaceholder` — no props.

- [ ] **Step 1: Create the component**

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
</script>

<div class="flex flex-col items-center justify-center text-center gap-2 py-10">
	<span class="text-gray-300 dark:text-gray-600"><Icon name="list" size={28} /></span>
	<div class="text-sm font-medium text-gray-500 dark:text-gray-400">Subtasks coming soon</div>
	<div class="text-xs text-gray-400 max-w-[16rem]">
		Break this task into smaller steps. We'll wire this up next.
	</div>
</div>
```

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: no new errors in `SubtasksPlaceholder.svelte`.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/workos/views/detail/SubtasksPlaceholder.svelte
git commit -m "feat(workos): add subtasks placeholder for task detail"
```

---

### Task 5: AssigneeField

Avatar + name display that opens a DropdownMenu of directory users. Single assignee.

**Files:**
- Create: `src/lib/components/workos/views/detail/AssigneeField.svelte`

**Interfaces:**
- Consumes: `Task` type; store exports `directory`, `displayName`, `initials`, `editTask`.
- Produces: `AssigneeField` with prop `task: Task`.

- [ ] **Step 1: Create the component**

```svelte
<script lang="ts">
	import { Avatar, AvatarFallback } from '$lib/components/ui/avatar';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import Icon from '../../ui/Icon.svelte';
	import { directory, displayName, initials, editTask } from '../../lib/store';
	import type { Task } from '../../lib/types';

	export let task: Task;

	$: assigned = task.assignee_id ?? null;
	$: members = Object.entries($directory).map(([id, u]) => ({ id, name: u.name }));

	const fallback = 'bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300';

	function assign(id: string | null) {
		editTask(task.id, { assignee_id: id });
	}
</script>

<DropdownMenu.Root>
	<DropdownMenu.Trigger
		class="inline-flex items-center gap-2 rounded-md px-1 -mx-1 py-0.5 hover:bg-gray-100 dark:hover:bg-gray-900"
	>
		{#if assigned}
			<Avatar size="sm">
				<AvatarFallback class="{fallback} text-[11px]">{initials(assigned)}</AvatarFallback>
			</Avatar>
			<span class="text-sm">{displayName(assigned)}</span>
		{:else}
			<span class="inline-flex items-center gap-1.5 text-sm text-gray-400">
				<Icon name="user" size={15} /> Unassigned
			</span>
		{/if}
	</DropdownMenu.Trigger>
	<DropdownMenu.Content class="max-h-64 overflow-y-auto">
		<DropdownMenu.Item onSelect={() => assign(null)}>Unassigned</DropdownMenu.Item>
		{#each members as m (m.id)}
			<DropdownMenu.Item onSelect={() => assign(m.id)}>
				<span class="inline-flex items-center gap-2">
					<Avatar size="sm" class="size-5">
						<AvatarFallback class="{fallback} text-[10px]">{initials(m.id)}</AvatarFallback>
					</Avatar>
					{m.name}
				</span>
			</DropdownMenu.Item>
		{/each}
		{#if !members.length}<DropdownMenu.Item disabled>No members</DropdownMenu.Item>{/if}
	</DropdownMenu.Content>
</DropdownMenu.Root>
```

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: no new errors in `AssigneeField.svelte`. (If `onSelect` is flagged, confirm the prop name against `src/lib/components/ui/dropdown-menu/dropdown-menu-item.svelte` — bits-ui v2 menu items use `onSelect`.)

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/workos/views/detail/AssigneeField.svelte
git commit -m "feat(workos): add AssigneeField for task detail"
```

---

### Task 6: AttachmentsPanel

Card grid of files with "Download All", per-file Download, an add (+) card, and gated delete. Supersedes `AttachmentList.svelte`'s styling.

**Files:**
- Create: `src/lib/components/workos/views/detail/AttachmentsPanel.svelte`

**Interfaces:**
- Consumes: store exports `attachments`, `removeAttachment`, `uploadFiles`, `roles`, `currentTeam`, `selectedTaskId`; `canDeleteAttachment` from `lib/roles`; `attachmentUrl` from `lib/api`; `user` from `$lib/stores`.
- Produces: `AttachmentsPanel` — no props (reads `selectedTaskId`/`attachments` from the store).

- [ ] **Step 1: Create the component**

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import * as Card from '$lib/components/ui/card';
	import {
		attachments,
		removeAttachment,
		uploadFiles,
		roles,
		currentTeam,
		selectedTaskId
	} from '../../lib/store';
	import { user } from '$lib/stores';
	import { canDeleteAttachment } from '../../lib/roles';
	import * as api from '../../lib/api';

	$: myRole = $currentTeam ? $roles[$currentTeam.id] : undefined;
	$: files = $attachments.filter((a) => !a.comment_id);

	const isImage = (ct?: string | null) => !!ct && ct.startsWith('image/');
	const kb = (n: number) => `${Math.max(1, Math.round(n / 1024))} KB`;

	let fileInput: HTMLInputElement;

	function downloadAll() {
		for (const a of files) {
			const link = document.createElement('a');
			link.href = api.attachmentUrl(a.id);
			link.download = a.name;
			link.target = '_blank';
			document.body.appendChild(link);
			link.click();
			link.remove();
		}
	}

	async function onFiles(e: Event) {
		const fl = (e.target as HTMLInputElement).files;
		const taskId = $selectedTaskId;
		if (fl && fl.length && taskId) await uploadFiles(taskId, fl);
		(e.target as HTMLInputElement).value = '';
	}
</script>

<div class="pt-4">
	<div class="flex items-center justify-between mb-2">
		<div class="flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-gray-300">
			<Icon name="paperclip" size={15} /> Attachment ({files.length})
		</div>
		{#if files.length}
			<button
				class="inline-flex items-center gap-1 text-xs text-teal-600 hover:text-teal-700"
				onclick={downloadAll}
			>
				<Icon name="download" size={13} /> Download All
			</button>
		{/if}
	</div>

	<div class="grid grid-cols-2 gap-2">
		{#each files as a (a.id)}
			<Card.Root class="p-2.5 flex flex-row items-center gap-2 group rounded-xl">
				{#if isImage(a.content_type)}
					<img src={api.attachmentUrl(a.id)} alt={a.name} class="w-9 h-9 rounded object-cover flex-none" />
				{:else}
					<span class="w-9 h-9 rounded bg-gray-100 dark:bg-gray-800 flex items-center justify-center flex-none text-gray-500">
						<Icon name="file" size={18} />
					</span>
				{/if}
				<div class="min-w-0 flex-1">
					<div class="text-xs font-medium truncate">{a.name}</div>
					<div class="text-[11px] text-gray-400 flex items-center gap-1">
						{kb(a.size)} ·
						<a class="text-teal-600 hover:underline" href={api.attachmentUrl(a.id)} target="_blank" rel="noreferrer">Download</a>
					</div>
				</div>
				{#if canDeleteAttachment(a, $user?.id ?? '', myRole)}
					<button class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 flex-none" title="Remove" onclick={() => removeAttachment(a.id)}>
						<Icon name="trash" size={13} />
					</button>
				{/if}
			</Card.Root>
		{/each}
		<button
			class="flex items-center justify-center rounded-xl border border-dashed border-gray-300 dark:border-gray-700 text-gray-400 hover:border-teal-500 hover:text-teal-600 min-h-[64px]"
			onclick={() => fileInput.click()}
			title="Add attachment"
		>
			<Icon name="plus" size={18} />
		</button>
	</div>

	<input type="file" multiple class="hidden" bind:this={fileInput} onchange={onFiles} />
</div>
```

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: no new errors in `AttachmentsPanel.svelte`.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/workos/views/detail/AttachmentsPanel.svelte
git commit -m "feat(workos): add AttachmentsPanel card grid for task detail"
```

---

### Task 7: DetailHeader

Header bar: parked expand glyph + breadcrumb on the left; pencil (edit title), share (copy link), `…` (delete), and close on the right.

**Files:**
- Create: `src/lib/components/workos/views/detail/DetailHeader.svelte`

**Interfaces:**
- Consumes: `Task` + `STATUS_LABEL` from `lib/types`; store exports `currentWorkstream`, `closeTask`, `removeTask`, `roles`, `currentTeam`; `canDeleteTask` from `lib/roles`; `user` from `$lib/stores`; `Button` + `buttonVariants` from `$lib/components/ui/button`; `cn` from `$lib/components/ui/utils.js`.
- Produces: `DetailHeader` with props `task: Task`, `onEditTitle: () => void`.

- [ ] **Step 1: Create the component**

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { Button, buttonVariants } from '$lib/components/ui/button';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { cn } from '$lib/components/ui/utils.js';
	import { STATUS_LABEL, type Task } from '../../lib/types';
	import { currentWorkstream, closeTask, removeTask, roles, currentTeam } from '../../lib/store';
	import { user } from '$lib/stores';
	import { canDeleteTask } from '../../lib/roles';

	export let task: Task;
	export let onEditTitle: () => void;

	$: myRole = $currentTeam ? $roles[$currentTeam.id] : undefined;
	$: crumb = $currentWorkstream?.name ?? 'Tasks';

	let copied = false;
	async function copyLink() {
		try {
			await navigator.clipboard.writeText(window.location.href);
			copied = true;
			setTimeout(() => (copied = false), 1500);
		} catch {
			/* clipboard unavailable */
		}
	}
</script>

<div class="flex items-center gap-1 px-2.5 h-12 border-b border-gray-200 dark:border-gray-800">
	<Button variant="ghost" size="icon-sm" title="Expand" class="text-gray-400">
		<Icon name="maximize" size={16} />
	</Button>
	<div class="flex items-center gap-1.5 min-w-0 text-xs text-gray-400">
		<span class="truncate">{crumb}</span>
		<Icon name="chevron-right" size={12} />
		<span class="truncate text-gray-500 dark:text-gray-300">{STATUS_LABEL[task.status]}</span>
	</div>
	<div class="flex-1"></div>
	<Button variant="ghost" size="icon-sm" title="Edit title" class="text-gray-500" onclick={onEditTitle}>
		<Icon name="pencil" size={15} />
	</Button>
	<Button variant="ghost" size="icon-sm" title={copied ? 'Copied!' : 'Copy link'} class="text-gray-500" onclick={copyLink}>
		<Icon name={copied ? 'check' : 'share-2'} size={15} />
	</Button>
	<DropdownMenu.Root>
		<DropdownMenu.Trigger title="More" class={cn(buttonVariants({ variant: 'ghost', size: 'icon-sm' }), 'text-gray-500')}>
			<Icon name="more-horizontal" size={16} />
		</DropdownMenu.Trigger>
		<DropdownMenu.Content align="end">
			{#if canDeleteTask(task, $user?.id ?? '', myRole)}
				<DropdownMenu.Item class="text-red-600" onSelect={() => removeTask(task.id)}>
					<span class="inline-flex items-center gap-2"><Icon name="trash" size={14} /> Delete task</span>
				</DropdownMenu.Item>
			{:else}
				<DropdownMenu.Item disabled>No actions available</DropdownMenu.Item>
			{/if}
		</DropdownMenu.Content>
	</DropdownMenu.Root>
	<Button variant="ghost" size="icon-sm" title="Close" class="text-gray-500" onclick={closeTask}>
		<Icon name="x" size={16} />
	</Button>
</div>
```

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: no new errors in `DetailHeader.svelte`. (If the `class` prop on `DropdownMenu.Trigger` is flagged, confirm it is forwarded in `src/lib/components/ui/dropdown-menu/dropdown-menu-trigger.svelte`.)

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/workos/views/detail/DetailHeader.svelte
git commit -m "feat(workos): add DetailHeader for task detail"
```

---

### Task 8: Rewrite TaskDetail + tabs, remove Feed

Compose the shell, title (click-to-edit), property rows (Status/Priority/Due date/Assignee/Tags/Progress/Description), attachments, and the Subtasks/Comments/Activities tabs. Delete the superseded `Feed.svelte`.

**Files:**
- Rewrite: `src/lib/components/workos/views/TaskDetail.svelte`
- Delete: `src/lib/components/workos/views/detail/Feed.svelte`

**Interfaces:**
- Consumes: Tasks 3–7 components; `formatDateLong` (Task 1); store exports `selectedTask`, `closeTask`, `editTask`, `labels`, `comments`, `activity`; `STATUS_ORDER`, `STATUS_LABEL`, `PRIORITY_ORDER`, `TaskStatus`, `TaskPriority` from `lib/types`; shadcn `Tabs`, `DropdownMenu`, `Badge`; existing `Pills`, `StatusDot`, `Icon`, `CommentItem`, `CommentComposer`, `ActivityItem`.

- [ ] **Step 1: Replace `TaskDetail.svelte` with the new implementation**

```svelte
<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import Pills from '../ui/Pills.svelte';
	import StatusDot from '../ui/StatusDot.svelte';
	import PropertyRow from './detail/PropertyRow.svelte';
	import DetailHeader from './detail/DetailHeader.svelte';
	import AssigneeField from './detail/AssigneeField.svelte';
	import AttachmentsPanel from './detail/AttachmentsPanel.svelte';
	import SubtasksPlaceholder from './detail/SubtasksPlaceholder.svelte';
	import CommentItem from './detail/CommentItem.svelte';
	import CommentComposer from './detail/CommentComposer.svelte';
	import ActivityItem from './detail/ActivityItem.svelte';
	import * as Tabs from '$lib/components/ui/tabs';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { Badge } from '$lib/components/ui/badge';
	import {
		STATUS_ORDER, STATUS_LABEL, PRIORITY_ORDER, type TaskStatus, type TaskPriority
	} from '../lib/types';
	import { formatDateLong } from '../lib/format';
	import { selectedTask, closeTask, editTask, labels, comments, activity } from '../lib/store';

	$: t = $selectedTask;
	$: sortedComments = [...$comments].sort((a, b) => a.created_at - b.created_at);
	$: sortedActivity = [...$activity].sort((a, b) => a.created_at - b.created_at);

	const STATUS_COLOR: Record<string, string> = {
		backlog: '#9ca3af', todo: '#6b7280', in_progress: '#2563eb',
		in_review: '#7c3aed', done: '#16a34a', canceled: '#9ca3af'
	};
	function statusShape(s: TaskStatus): 'check' | 'half' | 'x' | 'ring' {
		if (s === 'done') return 'check';
		if (s === 'in_progress') return 'half';
		if (s === 'canceled') return 'x';
		return 'ring';
	}

	let editingTitle = false;
	let titleDraft = '';
	let editingDue = false;
	let editingProgress = false;
	let editingDesc = false;
	let descDraft = '';
	$: if (t && !editingDesc) descDraft = t.description ?? '';

	function startTitle() {
		if (t) {
			titleDraft = t.title;
			editingTitle = true;
		}
	}
	function commitTitle() {
		if (t && titleDraft.trim() && titleDraft.trim() !== t.title) editTask(t.id, { title: titleDraft.trim() });
		editingTitle = false;
	}
	function toggleLabel(id: string) {
		if (!t) return;
		const has = t.labels.includes(id);
		editTask(t.id, { labels: has ? t.labels.filter((x) => x !== id) : [...t.labels, id] });
	}
</script>

{#if t}
	<div class="absolute inset-0 z-30 flex justify-end">
		<div class="absolute inset-0 bg-black/30" onclick={closeTask} role="presentation"></div>
		<div class="relative w-[460px] max-w-[92%] h-full bg-white dark:bg-gray-950 border-l border-gray-200 dark:border-gray-800 shadow-xl flex flex-col">
			<DetailHeader task={t} onEditTitle={startTitle} />

			<div class="flex-1 overflow-y-auto p-4">
				<!-- Title -->
				{#if editingTitle}
					<!-- svelte-ignore a11y_autofocus -->
					<input
						class="w-full text-xl font-semibold bg-transparent mb-5 focus:outline-none border-b border-teal-500"
						bind:value={titleDraft}
						onblur={commitTitle}
						onkeydown={(e) => {
							if (e.key === 'Enter') commitTitle();
							if (e.key === 'Escape') editingTitle = false;
						}}
						autofocus
					/>
				{:else}
					<button class="w-full text-left text-xl font-semibold mb-5 hover:opacity-80" onclick={startTitle}>
						{t.title}
					</button>
				{/if}

				<!-- Properties -->
				<div class="space-y-1.5 pb-4 border-b border-gray-200 dark:border-gray-800">
					<!-- Status -->
					<PropertyRow icon="circle" label="Status">
						<DropdownMenu.Root>
							<DropdownMenu.Trigger class="inline-flex items-center gap-2 rounded-md px-1 -mx-1 py-0.5 hover:bg-gray-100 dark:hover:bg-gray-900">
								<StatusDot shape={statusShape(t.status)} color={STATUS_COLOR[t.status]} />
								<span>{STATUS_LABEL[t.status]}</span>
							</DropdownMenu.Trigger>
							<DropdownMenu.Content>
								{#each STATUS_ORDER as s (s)}
									<DropdownMenu.Item onSelect={() => editTask(t.id, { status: s })}>
										<span class="inline-flex items-center gap-2">
											<StatusDot shape={statusShape(s)} color={STATUS_COLOR[s]} /> {STATUS_LABEL[s]}
										</span>
									</DropdownMenu.Item>
								{/each}
								<DropdownMenu.Item onSelect={() => editTask(t.id, { status: 'canceled' as TaskStatus })}>
									<span class="inline-flex items-center gap-2">
										<StatusDot shape="x" color={STATUS_COLOR.canceled} /> Canceled
									</span>
								</DropdownMenu.Item>
							</DropdownMenu.Content>
						</DropdownMenu.Root>
					</PropertyRow>

					<!-- Priority -->
					<PropertyRow icon="flag" label="Priority">
						<DropdownMenu.Root>
							<DropdownMenu.Trigger class="inline-flex items-center gap-2 rounded-md px-1 -mx-1 py-0.5 hover:bg-gray-100 dark:hover:bg-gray-900">
								{#if t.priority}<Pills priority={t.priority} />{:else}<span class="text-gray-400">No priority</span>{/if}
							</DropdownMenu.Trigger>
							<DropdownMenu.Content>
								<DropdownMenu.Item onSelect={() => editTask(t.id, { priority: null })}>No priority</DropdownMenu.Item>
								{#each PRIORITY_ORDER as p (p)}
									<DropdownMenu.Item onSelect={() => editTask(t.id, { priority: p as TaskPriority })}>
										<Pills priority={p} />
									</DropdownMenu.Item>
								{/each}
							</DropdownMenu.Content>
						</DropdownMenu.Root>
					</PropertyRow>

					<!-- Due date -->
					<PropertyRow icon="calendar" label="Due date">
						{#if editingDue}
							<!-- svelte-ignore a11y_autofocus -->
							<input
								type="date"
								class="text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded px-2 py-1"
								value={t.due_date ? new Date(t.due_date).toISOString().slice(0, 10) : ''}
								onchange={(e) => {
									const v = (e.target as HTMLInputElement).value;
									editTask(t.id, { due_date: v ? new Date(v).getTime() : null });
									editingDue = false;
								}}
								onblur={() => (editingDue = false)}
								autofocus
							/>
						{:else}
							<button
								class="rounded-md px-1 -mx-1 py-0.5 hover:bg-gray-100 dark:hover:bg-gray-900 {t.due_date ? '' : 'text-gray-400'}"
								onclick={() => (editingDue = true)}
							>
								{t.due_date ? formatDateLong(t.due_date) : 'Add due date'}
							</button>
						{/if}
					</PropertyRow>

					<!-- Assignee -->
					<PropertyRow icon="user" label="Assignee">
						<AssigneeField task={t} />
					</PropertyRow>

					<!-- Tags -->
					<PropertyRow icon="tag" label="Tags" align="start">
						<div class="flex flex-wrap items-center gap-1.5">
							{#each $labels.filter((l) => t.labels.includes(l.id)) as l (l.id)}
								<Pills label={l} />
							{/each}
							<DropdownMenu.Root>
								<DropdownMenu.Trigger class="inline-flex items-center gap-1 text-xs text-gray-400 rounded-md px-1.5 py-0.5 border border-dashed border-gray-300 dark:border-gray-700 hover:border-teal-500 hover:text-teal-600">
									<Icon name="plus" size={12} />{#if !t.labels.length}<span>Add tags</span>{/if}
								</DropdownMenu.Trigger>
								<DropdownMenu.Content class="max-h-64 overflow-y-auto">
									{#each $labels as l (l.id)}
										<DropdownMenu.Item closeOnSelect={false} onSelect={() => toggleLabel(l.id)}>
											<span class="inline-flex items-center gap-2">
												<span class="w-3.5 inline-flex">{#if t.labels.includes(l.id)}<Icon name="check" size={13} />{/if}</span>
												<span class="w-2 h-2 rounded-full" style="background:{l.color}"></span>
												{l.name}
											</span>
										</DropdownMenu.Item>
									{/each}
									{#if !$labels.length}<DropdownMenu.Item disabled>No labels yet</DropdownMenu.Item>{/if}
								</DropdownMenu.Content>
							</DropdownMenu.Root>
						</div>
					</PropertyRow>

					<!-- Progress -->
					<PropertyRow icon="loader" label="Progress">
						{#if editingProgress}
							<div class="flex items-center gap-2">
								<input
									type="range" min="0" max="100" step="5" value={t.progress}
									onchange={(e) => editTask(t.id, { progress: parseInt((e.target as HTMLInputElement).value, 10) })}
								/>
								<span class="text-sm w-9">{t.progress}%</span>
								<button class="text-xs text-teal-600" onclick={() => (editingProgress = false)}>Done</button>
							</div>
						{:else}
							<button
								class="flex items-center gap-2 w-full rounded-md px-1 -mx-1 py-0.5 hover:bg-gray-100 dark:hover:bg-gray-900"
								onclick={() => (editingProgress = true)}
							>
								<span class="flex-1 h-1.5 rounded-full bg-gray-200 dark:bg-gray-800 overflow-hidden max-w-[140px]">
									<span class="block h-full bg-teal-500 rounded-full" style="width:{t.progress}%"></span>
								</span>
								<span class="text-sm text-gray-500">{t.progress}%</span>
							</button>
						{/if}
					</PropertyRow>
				</div>

				<!-- Description -->
				<div class="pt-4">
					<div class="flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-gray-300 mb-2">
						<Icon name="align-left" size={15} /> Description
					</div>
					{#if editingDesc}
						<textarea class="w-full text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded-lg p-2.5 min-h-24" bind:value={descDraft}></textarea>
						<div class="flex gap-2 mt-2">
							<button class="text-sm px-3 py-1 rounded-md bg-teal-600 text-white" onclick={() => { editTask(t.id, { description: descDraft }); editingDesc = false; }}>Save</button>
							<button class="text-sm px-3 py-1 rounded-md border border-gray-300 dark:border-gray-700" onclick={() => (editingDesc = false)}>Cancel</button>
						</div>
					{:else}
						<button
							class="block w-full text-left text-sm text-gray-600 dark:text-gray-300 whitespace-pre-wrap rounded-lg border border-gray-200 dark:border-gray-800 p-3 hover:border-gray-300 dark:hover:border-gray-700"
							onclick={() => (editingDesc = true)}
						>
							{t.description || 'Add a description…'}
						</button>
					{/if}
				</div>

				<!-- Attachments -->
				<AttachmentsPanel />

				<!-- Tabs -->
				<div class="pt-5">
					<Tabs.Root value="comments">
						<Tabs.List variant="line" class="w-full justify-start gap-4 border-b border-gray-200 dark:border-gray-800 bg-transparent p-0">
							<Tabs.Trigger value="subtasks">Subtasks</Tabs.Trigger>
							<Tabs.Trigger value="comments" class="gap-1.5">
								Comments
								{#if sortedComments.length}<Badge variant="secondary" class="px-1.5 py-0">{sortedComments.length}</Badge>{/if}
							</Tabs.Trigger>
							<Tabs.Trigger value="activities">Activities</Tabs.Trigger>
						</Tabs.List>

						<Tabs.Content value="subtasks"><SubtasksPlaceholder /></Tabs.Content>

						<Tabs.Content value="comments">
							<div class="divide-y divide-gray-100 dark:divide-gray-900">
								{#each sortedComments as c (c.id)}<CommentItem comment={c} />{/each}
							</div>
							<CommentComposer taskId={t.id} />
						</Tabs.Content>

						<Tabs.Content value="activities">
							<div class="pt-2">
								{#each sortedActivity as a (a.id)}<ActivityItem activity={a} />{/each}
								{#if !sortedActivity.length}<div class="text-xs text-gray-400 py-4 text-center">No activity yet</div>{/if}
							</div>
						</Tabs.Content>
					</Tabs.Root>
				</div>
			</div>
		</div>
	</div>
{/if}
```

- [ ] **Step 2: Delete the superseded Feed component**

```bash
git rm src/lib/components/workos/views/detail/Feed.svelte
```

- [ ] **Step 3: Verify nothing else imports Feed**

Run: `grep -rn "detail/Feed" src/` (or use your search tool)
Expected: no matches.

- [ ] **Step 4: Type-check**

Run: `npm run check`
Expected: no new errors in `TaskDetail.svelte`. Resolve any genuinely new errors introduced by this task before committing.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/views/TaskDetail.svelte
git commit -m "feat(workos): redesign task detail panel with shadcn primitives + tabs"
```

---

### Task 9: Verification & browser smoke

Prove the redesign works end-to-end and didn't regress logic.

**Files:** none (verification only).

- [ ] **Step 1: Run the frontend test suite**

Run: `npm run test:frontend`
Expected: all WorkOS lib tests pass (including the new `formatDateLong` cases). No tests reference the panel markup, so none should break.

- [ ] **Step 2: Full type-check**

Run: `npm run check`
Expected: no errors in any of the files created/modified in Tasks 1–8.

- [ ] **Step 3: Browser smoke via the dev preview**

Start the dev server (`preview_start`), open the WorkOS tool, open a task. Capture evidence and confirm:
- Header: expand glyph + breadcrumb `workstream / status` on the left; pencil/share/`…`/close on the right. Clicking share shows the "Copied!" check; clicking the pencil focuses the title input.
- Property rows render read-first; clicking Status/Priority/Assignee/Tags opens a themed DropdownMenu; Due date reveals a date input; Progress reveals the slider; Description opens the textarea editor. Each edit persists (reflected after re-open).
- Attachments: card grid, per-file Download, Download All, and the `+` add card (upload a file). 
- Tabs: Subtasks placeholder, Comments (with count badge + composer), Activities list.
- Toggle dark mode (`preview_resize` / theme) and confirm all surfaces, dropdowns, and the teal accents read correctly.

Take `preview_screenshot`s of each tab in light and dark mode to share as proof.

- [ ] **Step 4: Final commit (if any smoke fixes were needed)**

```bash
git add -A
git commit -m "fix(workos): task detail redesign smoke fixes"
```

---

## Self-Review

**Spec coverage:**
- Read-first click-to-edit → Tasks 5, 8 (DropdownMenu triggers + inline reveals). ✓
- shadcn-svelte primitives → Avatar (T5), Card (T6), Button/DropdownMenu (T7), Tabs/Badge/DropdownMenu (T8). ✓
- Keep Priority & Progress rows → Task 8. ✓
- Header: expand parked, pencil/share(copy)/`…`(delete), close far right → Task 7. ✓
- Tabs split (Subtasks placeholder / Comments / Activities), remove Feed → Tasks 4, 8. ✓
- Attachments card grid + Download All + add → Task 6. ✓
- Osool teal accent, dark mode → Global Constraints, applied throughout. ✓
- Breadcrumb `workstream / status`, long date format → Tasks 1, 7, 8. ✓
- Verification (tests + browser smoke) → Task 9. ✓

**Placeholder scan:** No "TBD"/"implement later". Subtasks placeholder is intentional scope, fully specified (Task 4). All code blocks are complete.

**Type consistency:** Store/role/api signatures (`editTask`, `removeTask`, `uploadFiles`, `removeAttachment`, `attachmentUrl`, `canDeleteTask`, `canDeleteAttachment`, `initials`, `displayName`) match their definitions. `formatDateLong(ts: number): string` defined in T1, consumed in T8. Component props (`PropertyRow {icon,label,align}`, `AssigneeField {task}`, `DetailHeader {task,onEditTitle}`) match call sites. `StatusDot` shapes (`check|half|x|ring|dashed`) and `Pills` props (`priority|label`) match their components.

**Risk notes for the executor:**
- bits-ui v2 prop names: menu items use `onSelect` and support `closeOnSelect`; if `npm run check` flags either, verify against the local `dropdown-menu-item.svelte`.
- `DropdownMenu.Trigger` forwards `class` and renders a `<button>`; the `buttonVariants(...)` class pattern (Task 7) gives it button styling without the `child` snippet.
- Avatar fallback/size props (`size="sm"`) come from the local `avatar.svelte`.
