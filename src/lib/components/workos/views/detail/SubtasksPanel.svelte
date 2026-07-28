<script lang="ts">
	import { tick } from 'svelte';
	import { toast } from 'svelte-sonner';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import Icon from '../../ui/Icon.svelte';
	import { Button } from '$lib/components/ui/button';
	import AssigneeAvatars from '../AssigneeAvatars.svelte';
	import { subtasks, addSubtask, editSubtask, removeSubtask, directory, roles } from '../../lib/store';
	import { toggleAssignee } from '../../lib/assignees';
	import { canEditTask } from '../../lib/roles';
	import { user } from '$lib/stores';
	import type { Task, Subtask } from '../../lib/types';
	import { computeSortKey, resolveRename, type SortKeyUpdate } from '../../lib/subtaskPanel';

	export let task: Task;

	let title = '';
	let renamingId: string | null = null;
	let draft = '';
	let confirmingId: string | null = null; // row showing the inline delete confirm

	function startRename(subtask: Subtask) {
		renamingId = subtask.id;
		draft = subtask.title;
	}

	// Null renamingId BEFORE acting so the input's blur (fired by unmount)
	// can't double-commit.
	function commitRename(subtask: Subtask) {
		if (renamingId !== subtask.id) return;
		renamingId = null;
		const res = resolveRename(subtask.title, draft);
		if (res.action === 'commit')
			void editSubtask(subtask.id, { title: res.title }).catch(notifyFailed);
	}

	function cancelRename() {
		renamingId = null;
	}

	// Panel-local sorted view: the store appends realtime/created rows at the end;
	// sorting here keeps display order canonical and makes sort_key edits
	// (reorder, concurrent editors) re-flow automatically.
	$: sorted = [...$subtasks].sort((a, b) => a.sort_key - b.sort_key);

	$: parentIds = task.assignee_ids ?? [];
	$: members = Object.entries($directory).map(([id, u]) => ({ id, name: u.name }));
	$: onTask = members.filter((m) => parentIds.includes(m.id));
	$: everyoneElse = members.filter((m) => !parentIds.includes(m.id));
	// Whether the viewer may expand the parent's assignee list (mirrors the
	// server's task.write gate on auto-add; workspace-admin edge under-shown,
	// server remains authoritative).
	$: canExpand =
		$user?.role === 'admin' || canEditTask(task, $user?.id ?? '', $roles[task.team_id], undefined);

	// Store calls roll back optimistically on failure — surface it, InboxView-style.
	const notifyFailed = () => toast.error("Couldn't update — try again");

	async function submit() {
		const value = title.trim();
		if (!value) return;
		title = '';
		try {
			await addSubtask(task.id, value);
		} catch {
			notifyFailed();
			if (!title) title = value; // restore the draft so a failed create isn't lost
		}
	}

	function toggle(subtask: Subtask, id: string) {
		void editSubtask(subtask.id, { assignee_ids: toggleAssignee(subtask.assignee_ids, id) }).catch(
			notifyFailed
		);
	}

	// Grow a textarea to fit its content; the param ties re-measuring to the
	// bound value so programmatic clears (submit) shrink it back.
	function autogrow(el: HTMLTextAreaElement, _value: string) {
		const resize = () => {
			el.style.height = 'auto';
			el.style.height = `${el.scrollHeight}px`;
		};
		resize();
		return { update: resize };
	}

	// Browsers insert a newline for Shift+Enter natively but not Alt+Enter —
	// do it by hand and fire input so bind:value stays in sync.
	function insertNewline(el: HTMLTextAreaElement) {
		const start = el.selectionStart;
		const end = el.selectionEnd;
		el.value = el.value.slice(0, start) + '\n' + el.value.slice(end);
		el.selectionStart = el.selectionEnd = start + 1;
		el.dispatchEvent(new Event('input'));
	}

	let dragIndex: number | null = null;
	let dropIndex: number | null = null; // gap index 0..n in the sorted list
	let rowEls: HTMLElement[] = [];

	function dragStart(i: number, e: PointerEvent) {
		if (e.button !== 0) return;
		dragIndex = i;
		dropIndex = null;
		(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
	}

	function dragMove(e: PointerEvent) {
		if (dragIndex === null) return;
		let gap = sorted.length;
		for (let i = 0; i < sorted.length; i++) {
			const el = rowEls[i];
			if (!el) continue;
			const r = el.getBoundingClientRect();
			if (e.clientY < r.top + r.height / 2) {
				gap = i;
				break;
			}
		}
		dropIndex = gap;
	}

	function dragEnd() {
		if (dragIndex === null) return;
		const from = dragIndex;
		const gap = dropIndex;
		dragIndex = null;
		dropIndex = null;
		if (gap === null) return;
		// gap is an insertion point in the list INCLUDING the dragged row;
		// removing that row first shifts positions after it down by one.
		const to = gap > from ? gap - 1 : gap;
		void applyReorder(computeSortKey(sorted, from, to));
	}

	async function applyReorder(updates: SortKeyUpdate[]) {
		if (!updates.length) return;
		const results = await Promise.allSettled(
			updates.map((u) => editSubtask(u.id, { sort_key: u.sort_key }))
		);
		// One toast per batch even if several row PATCHes fail (renumber case).
		if (results.some((r) => r.status === 'rejected')) notifyFailed();
	}

	async function moveByKeyboard(i: number, e: KeyboardEvent) {
		if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
		e.preventDefault();
		const to = e.key === 'ArrowUp' ? i - 1 : i + 1;
		if (to < 0 || to >= sorted.length) return;
		void applyReorder(computeSortKey(sorted, i, to));
		// The optimistic sort_key write re-sorts the keyed each, which moves and
		// blurs the focused handle — put focus back on it at its new position.
		await tick();
		rowEls[to]?.querySelector<HTMLButtonElement>('.wos-drag')?.focus();
	}
</script>

<div class="pt-4 space-y-2">
	<div class="divide-y divide-gray-100 dark:divide-gray-900">
		{#each sorted as subtask, i (subtask.id)}
			{#if dragIndex !== null && dropIndex === i}
				<div class="h-0.5 rounded bg-primary"></div>
			{/if}
			<div
				bind:this={rowEls[i]}
				class="group flex items-start gap-2 px-0.5 py-1.5 transition-colors hover:bg-gray-50 dark:hover:bg-gray-900/40 {dragIndex ===
				i
					? 'opacity-50'
					: subtask.completed
						? 'opacity-75'
						: ''}"
			>
				{#if confirmingId === subtask.id}
				<div
					class="flex min-w-0 flex-1 items-center gap-2 rounded-md bg-red-50 px-2 py-1 text-xs text-red-800 dark:bg-red-950/40 dark:text-red-300"
				>
					<span class="min-w-0 truncate">Delete "{subtask.title}"?</span>
					<div class="ml-auto flex shrink-0 items-center gap-1.5">
						<Button
							variant="destructive"
							size="xs"
							onclick={() => {
								confirmingId = null;
								void removeSubtask(subtask.id).catch(notifyFailed);
							}}
						>
							Delete
						</Button>
						<Button variant="outline" size="xs" onclick={() => (confirmingId = null)}>Cancel</Button>
					</div>
				</div>
				{:else}
				<button
					type="button"
					class="wos-drag -ml-0.5 mt-[3px] shrink-0 cursor-grab touch-none text-gray-300 transition-colors hover:text-gray-500 active:cursor-grabbing dark:text-gray-600 dark:hover:text-gray-400"
					aria-label="Reorder subtask (Arrow keys to move)"
					onpointerdown={(e) => dragStart(i, e)}
					onpointermove={dragMove}
					onpointerup={dragEnd}
					onpointercancel={dragEnd}
					onkeydown={(e) => moveByKeyboard(i, e)}
				>
					<Icon name="grip-vertical" size={12} />
				</button>
				<button
					type="button"
					role="checkbox"
					aria-checked={subtask.completed}
					aria-label="Toggle subtask completion"
					class="mt-[2px] flex size-[15px] shrink-0 items-center justify-center rounded-full border-[1.5px] transition-colors {subtask.completed
						? 'border-primary bg-primary text-primary-foreground'
						: 'border-gray-300 hover:border-gray-400 dark:border-gray-600 dark:hover:border-gray-500'}"
					onclick={() =>
						void editSubtask(subtask.id, { completed: !subtask.completed }).catch(notifyFailed)}
				>
					{#if subtask.completed}
						<span class="wos-subcheck-pop"><Icon name="check" size={10} /></span>
					{/if}
				</button>
				{#if renamingId === subtask.id}
					<!-- svelte-ignore a11y_autofocus -->
					<textarea
						class="min-w-0 flex-1 resize-none overflow-hidden bg-transparent text-[13px] leading-[19px] outline-none"
						aria-label="Rename subtask"
						rows={1}
						bind:value={draft}
						use:autogrow={draft}
						autofocus
						onkeydown={(e) => {
							if (e.key === 'Enter') {
								if (e.altKey) {
									e.preventDefault();
									insertNewline(e.currentTarget);
								} else if (!e.shiftKey) {
									e.preventDefault();
									commitRename(subtask);
								}
							}
							if (e.key === 'Escape') {
								e.stopPropagation();
								cancelRename();
							}
						}}
						onblur={() => commitRename(subtask)}
					></textarea>
				{:else}
					<button
						type="button"
						class="min-w-0 flex-1 whitespace-pre-wrap break-words text-left text-[13px] leading-[19px] {subtask.completed
							? 'text-gray-400 line-through'
							: 'text-gray-900 dark:text-gray-100'}"
						title="Click to rename"
						onclick={() => startRename(subtask)}
					>
						{subtask.title}
					</button>
				{/if}
				<DropdownMenu.Root>
					<DropdownMenu.Trigger
						class="inline-flex items-center rounded-md p-0.5 hover:bg-gray-100 dark:hover:bg-gray-900"
						aria-label="Edit subtask assignees"
					>
						{#if (subtask.assignee_ids ?? []).length}
							<AssigneeAvatars ids={subtask.assignee_ids} size={18} max={3} />
						{:else}
							<span
								class="flex size-[18px] items-center justify-center rounded-full border-[1.5px] border-dashed border-gray-300 text-gray-400 dark:border-gray-700 dark:text-gray-500"
							>
								<Icon name="user-plus" size={11} />
							</span>
						{/if}
					</DropdownMenu.Trigger>
					<DropdownMenu.Content class="w-72 max-h-72 overflow-y-auto">
						<DropdownMenu.Label class="wos-caption text-gray-400">On this task</DropdownMenu.Label>
						{#each onTask as m (m.id)}
							<DropdownMenu.CheckboxItem
								checked={(subtask.assignee_ids ?? []).includes(m.id)}
								closeOnSelect={false}
								onCheckedChange={() => toggle(subtask, m.id)}
							>
								<span class="inline-flex items-center gap-2">
									<AssigneeAvatars ids={[m.id]} max={1} size={20} />
									{m.name}
								</span>
							</DropdownMenu.CheckboxItem>
						{/each}
						{#if !onTask.length}
							<DropdownMenu.Item disabled>No assignees on this task</DropdownMenu.Item>
						{/if}
						{#if canExpand && everyoneElse.length}
							<DropdownMenu.Separator />
							<DropdownMenu.Label class="wos-caption text-gray-400">Everyone else</DropdownMenu.Label>
							{#each everyoneElse as m (m.id)}
								<DropdownMenu.CheckboxItem
									checked={(subtask.assignee_ids ?? []).includes(m.id)}
									closeOnSelect={false}
									onCheckedChange={() => toggle(subtask, m.id)}
								>
									<span class="inline-flex min-w-0 flex-1 items-center gap-2">
										<AssigneeAvatars ids={[m.id]} max={1} size={20} />
										<span class="truncate">{m.name}</span>
										{#if (subtask.assignee_ids ?? []).includes(m.id)}
											<span
												class="wos-micro ml-auto rounded-full bg-amber-100 px-2 py-px text-amber-700 dark:bg-amber-950 dark:text-amber-400"
											>+ added to task</span>
										{/if}
									</span>
								</DropdownMenu.CheckboxItem>
							{/each}
							<DropdownMenu.Separator />
							<div class="flex items-center gap-1.5 px-2 py-1.5 text-[11px] text-gray-400 dark:text-gray-500">
								<Icon name="user-plus" size={12} /> Picking someone new also adds them to the task
							</div>
						{/if}
					</DropdownMenu.Content>
				</DropdownMenu.Root>
				<span
					class="wos-reveal opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100"
				>
					<Button
						variant="ghost"
						size="icon-xs"
						class="text-gray-400 hover:text-red-500"
						title="Delete subtask"
						onclick={() => (confirmingId = subtask.id)}
					>
						<Icon name="trash" size={13} />
					</Button>
				</span>
				{/if}
			</div>
		{/each}
		{#if dragIndex !== null && dropIndex === sorted.length}
			<div class="h-0.5 rounded bg-primary"></div>
		{/if}
	</div>

	{#if !sorted.length}
		<div class="flex flex-col items-center gap-1.5 py-6 text-center">
			<span class="flex size-8 items-center justify-center rounded-full bg-primary/10 text-primary">
				<Icon name="list-checks" size={16} />
			</span>
			<div class="text-[13px] font-medium text-gray-700 dark:text-gray-300">
				Break this task into smaller steps.
			</div>
			<div class="text-xs text-gray-400 dark:text-gray-500">Type below — Enter adds the next one.</div>
		</div>
	{/if}

	<div class="flex items-start gap-2 border-t border-gray-100 px-0.5 py-1.5 dark:border-gray-900">
		<span class="mt-[2px] text-primary"><Icon name="plus" size={14} /></span>
		<textarea
			class="min-w-0 flex-1 resize-none overflow-hidden bg-transparent text-[13px] leading-[19px] outline-none placeholder:text-gray-400"
			placeholder="Add a subtask — Enter adds another"
			aria-label="Add a subtask"
			rows={1}
			bind:value={title}
			use:autogrow={title}
			onkeydown={(e) => {
				if (e.key === 'Enter') {
					if (e.altKey) {
						e.preventDefault();
						insertNewline(e.currentTarget);
					} else if (!e.shiftKey) {
						e.preventDefault();
						void submit();
					}
				}
				if (e.key === 'Escape') {
					e.stopPropagation();
					title = '';
					e.currentTarget.blur();
				}
			}}
		></textarea>
	</div>
</div>

<style>
	.wos-subcheck-pop {
		display: flex;
		animation: wos-subcheck-pop 0.18s ease-out;
	}
	@keyframes wos-subcheck-pop {
		0% {
			transform: scale(0.4);
			opacity: 0;
		}
		70% {
			transform: scale(1.15);
		}
		100% {
			transform: scale(1);
			opacity: 1;
		}
	}
	/* Touch devices have no hover — keep controls visible, and reorder is
	   desktop-only (spec): hide the drag handle entirely. */
	@media (hover: none) {
		.wos-reveal {
			opacity: 1 !important;
		}
		.wos-drag {
			display: none;
		}
	}
</style>
