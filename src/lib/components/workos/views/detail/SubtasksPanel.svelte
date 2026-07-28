<script lang="ts">
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
	import { resolveRename } from '../../lib/subtaskPanel';

	export let task: Task;

	let title = '';
	let renamingId: string | null = null;
	let draft = '';

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
	$: doneCount = sorted.filter((s) => s.completed).length;

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
</script>

<div class="pt-4 space-y-3">
	{#if sorted.length}
		<div class="flex items-center gap-3">
			{#if sorted.length <= 24}
				<div class="flex flex-1 gap-[3px]">
					{#each sorted as s, i (s.id)}
						<div
							class="h-1.5 flex-1 rounded-[3px] transition-colors duration-300 {i < doneCount
								? 'bg-primary'
								: 'bg-gray-200 dark:bg-gray-800'}"
						></div>
					{/each}
				</div>
			{:else}
				<div class="h-1.5 flex-1 overflow-hidden rounded-[3px] bg-gray-200 dark:bg-gray-800">
					<div
						class="h-full rounded-[3px] bg-primary transition-[width] duration-300"
						style="width:{(doneCount / sorted.length) * 100}%"
					></div>
				</div>
			{/if}
			<span class="wos-micro rounded bg-primary/10 px-2 py-0.5 text-primary">
				{doneCount}/{sorted.length} done
			</span>
		</div>
	{/if}

	<div class="space-y-[5px]">
		{#each sorted as subtask (subtask.id)}
			<div
				class="group flex items-center gap-2.5 rounded-[10px] bg-gray-50 px-3 py-2.5 transition-colors hover:bg-gray-100 dark:bg-gray-900/50 dark:hover:bg-gray-800/60"
			>
				<button
					type="button"
					role="checkbox"
					aria-checked={subtask.completed}
					aria-label="Toggle subtask completion"
					class="flex size-[18px] shrink-0 items-center justify-center rounded-full border-2 transition-colors {subtask.completed
						? 'border-primary bg-primary text-primary-foreground'
						: 'border-gray-300 hover:border-gray-400 dark:border-gray-600 dark:hover:border-gray-500'}"
					onclick={() =>
						void editSubtask(subtask.id, { completed: !subtask.completed }).catch(notifyFailed)}
				>
					{#if subtask.completed}
						<span class="wos-subcheck-pop"><Icon name="check" size={11} /></span>
					{/if}
				</button>
				{#if renamingId === subtask.id}
					<!-- svelte-ignore a11y_autofocus -->
					<input
						class="min-w-0 flex-1 bg-transparent text-sm outline-none"
						aria-label="Rename subtask"
						bind:value={draft}
						autofocus
						onkeydown={(e) => {
							if (e.key === 'Enter') commitRename(subtask);
							if (e.key === 'Escape') cancelRename();
						}}
						onblur={() => commitRename(subtask)}
					/>
				{:else}
					<button
						type="button"
						class="min-w-0 flex-1 truncate text-left text-sm {subtask.completed
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
							<AssigneeAvatars ids={subtask.assignee_ids} size={20} max={3} />
						{:else}
							<span
								class="flex size-6 items-center justify-center rounded-full border-[1.5px] border-dashed border-gray-300 text-gray-400 dark:border-gray-700 dark:text-gray-500"
							>
								<Icon name="user-plus" size={13} />
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
						onclick={() => void removeSubtask(subtask.id).catch(notifyFailed)}
					>
						<Icon name="trash" size={14} />
					</Button>
				</span>
			</div>
		{/each}
	</div>

	{#if !sorted.length}
		<div class="flex flex-col items-center gap-1.5 py-8 text-center">
			<span class="flex size-9 items-center justify-center rounded-full bg-primary/10 text-primary">
				<Icon name="list-checks" size={18} />
			</span>
			<div class="text-sm font-medium text-gray-700 dark:text-gray-300">
				Break this task into smaller steps.
			</div>
			<div class="text-xs text-gray-400 dark:text-gray-500">Type below — Enter adds the next one.</div>
		</div>
	{/if}

	<div
		class="flex items-center gap-2 rounded-[10px] border-[1.5px] border-gray-200 bg-white px-3 py-2.5 transition-colors focus-within:border-primary dark:border-gray-800 dark:bg-gray-950"
	>
		<span class="text-primary"><Icon name="plus" size={15} /></span>
		<input
			class="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-gray-400"
			placeholder="Add a subtask — Enter adds another"
			aria-label="Add a subtask"
			bind:value={title}
			onkeydown={(e) => {
				if (e.key === 'Enter') void submit();
				if (e.key === 'Escape') {
					title = '';
					e.currentTarget.blur();
				}
			}}
		/>
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
	/* Touch devices have no hover — keep controls visible. */
	@media (hover: none) {
		.wos-reveal {
			opacity: 1 !important;
		}
	}
</style>
