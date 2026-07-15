<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog';
	import * as Select from '$lib/components/ui/select';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import Icon from '../ui/Icon.svelte';
	import StatusDot from '../ui/StatusDot.svelte';
	import Pills from '../ui/Pills.svelte';
	import AssigneeAvatars from './AssigneeAvatars.svelte';
	import { STATUS_ORDER, STATUS_LABEL, PRIORITY_ORDER, type TaskStatus, type TaskPriority } from '../lib/types';
	import { STATUS_COLOR, statusShape } from '../lib/colors';
	import { toggleAssignee } from '../lib/assignees';
	import { openModal, addTask, directory, labels, createLabel } from '../lib/store';

	$: req = $openModal?.kind === 'task' ? $openModal : null;

	let title = '';
	let assigneeIds: string[] = [];
	let description = '';
	let status: TaskStatus = 'backlog';
	let priority: TaskPriority | '' = '';
	let start = ''; // yyyy-mm-dd
	let due = '';
	let labelIds: string[] = [];
	let requireAttachment = false;
	let busy = false;
	let err = '';

	// Reset + apply prefill each time the dialog opens.
	let lastReq: typeof req = null;
	$: if (req !== lastReq) {
		lastReq = req;
		if (req) {
			title = '';
			assigneeIds = [];
			description = '';
			status = req.prefill?.status ?? 'backlog';
			priority = '';
			start = req.prefill?.start_date ? toDateInput(req.prefill.start_date) : '';
			due = req.prefill?.due_date ? toDateInput(req.prefill.due_date) : '';
			labelIds = [];
			labelQuery = '';
			creatingLabel = false;
			requireAttachment = false;
			busy = false;
			err = '';
		}
	}

	function toDateInput(ts: number): string {
		return new Date(ts).toISOString().slice(0, 10);
	}

	$: members = Object.entries($directory).map(([id, u]) => ({ id, name: u.name }));
	$: assigneeSummary =
		assigneeIds.length === 0 ? '' :
		assigneeIds.length === 1 ? ($directory[assigneeIds[0]]?.name ?? '1 assignee') :
		`${assigneeIds.length} assignees`;
	$: canSubmit = !!title.trim() && assigneeIds.length > 0 && !busy;

	function close() {
		openModal.set(null);
	}

	// Tag picker — mirrors the task-detail Tags row (search + create-new), but
	// toggles the local labelIds selection instead of patching a task.
	let labelQuery = '';
	let creatingLabel = false;
	$: filteredLabels = $labels.filter((l) =>
		l.name.toLowerCase().includes(labelQuery.trim().toLowerCase())
	);
	function toggleLabel(id: string) {
		labelIds = labelIds.includes(id) ? labelIds.filter((x) => x !== id) : [...labelIds, id];
	}
	async function createTagFromQuery() {
		const name = labelQuery.trim();
		if (!name || creatingLabel) return;
		creatingLabel = true;
		try {
			const created = await createLabel(name);
			if (created) {
				toggleLabel(created.id);
				labelQuery = '';
			}
		} finally {
			creatingLabel = false;
		}
	}
	function onLabelSearchKey(e: KeyboardEvent) {
		// Block the menu's typeahead from stealing focus/keystrokes from the input.
		e.stopPropagation();
		if (e.key === 'Enter') {
			e.preventDefault();
			createTagFromQuery();
		}
	}

	async function submit() {
		if (!req || !canSubmit) return;
		// Snapshot which dialog session this submit belongs to — if Cancel/Escape closes
		// this dialog and a new one opens before the request resolves, lastReq moves on
		// and the continuation below must not close/paint-error into the new session.
		const myReq = req;
		busy = true;
		err = '';
		try {
			await addTask(myReq.workstreamId, {
				title: title.trim(),
				assignee_ids: assigneeIds,
				description: description.trim() || undefined,
				status,
				priority: priority || null,
				start_date: start ? new Date(start).getTime() : null,
				due_date: due ? new Date(due).getTime() : null,
				labels: labelIds.length ? labelIds : undefined,
				attachment_required: requireAttachment
			});
			if (lastReq !== myReq) return; // a new dialog session opened while this create was in flight
			close();
		} catch (e: any) {
			if (lastReq !== myReq) return; // stale session — don't paint an error into the new dialog
			err = typeof e === 'string' ? e : (e?.detail ?? 'Could not create the task.');
		} finally {
			if (lastReq === myReq) busy = false;
		}
	}
</script>

<Dialog.Root open={req != null} onOpenChange={(o) => { if (!o) close(); }}>
	<Dialog.Content class="sm:max-w-lg rounded-2xl">
		<Dialog.Header>
			<Dialog.Title>New task</Dialog.Title>
			<Dialog.Description class="sr-only">Create a task — title and at least one assignee are required.</Dialog.Description>
		</Dialog.Header>

		{#if err}<div class="text-sm text-red-600">{err}</div>{/if}

		<div class="space-y-4">
			<!-- Title (required) -->
			<Input
				placeholder="Task title"
				bind:value={title}
				autofocus
				onkeydown={(e) => { if (e.key === 'Enter' && canSubmit) submit(); }}
			/>

			<!-- Assignees (required, multi-select) -->
			<div class="space-y-1">
				<DropdownMenu.Root>
					<DropdownMenu.Trigger
						class="w-full inline-flex items-center gap-2 rounded-md border border-gray-200 dark:border-gray-800 px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-900"
					>
						{#if assigneeIds.length}
							<AssigneeAvatars ids={assigneeIds} size={22} max={4} />
							<span>{assigneeSummary}</span>
						{:else}
							<span class="inline-flex items-center gap-1.5 text-gray-400">
								<Icon name="user" size={15} /> Assign to…
							</span>
						{/if}
						<span class="flex-1"></span>
						<Icon name="chevron-down" size={13} />
					</DropdownMenu.Trigger>
					<DropdownMenu.Content class="w-64 max-h-64 overflow-y-auto">
						{#each members as m (m.id)}
							<DropdownMenu.CheckboxItem
								checked={assigneeIds.includes(m.id)}
								closeOnSelect={false}
								onCheckedChange={() => (assigneeIds = toggleAssignee(assigneeIds, m.id))}
							>
								<span class="inline-flex items-center gap-2">
									<AssigneeAvatars ids={[m.id]} max={1} size={20} />
									{m.name}
								</span>
							</DropdownMenu.CheckboxItem>
						{/each}
						{#if !members.length}<DropdownMenu.Item disabled>No members</DropdownMenu.Item>{/if}
					</DropdownMenu.Content>
				</DropdownMenu.Root>
				{#if !assigneeIds.length}
					<p class="text-xs text-amber-600 dark:text-amber-500">At least one assignee is required.</p>
				{/if}
			</div>

			<!-- Description (optional) -->
			<textarea
				class="w-full min-h-[72px] text-sm rounded-md border border-gray-200 dark:border-gray-800 bg-transparent px-3 py-2 focus:outline-none focus:ring-1 focus:ring-primary"
				placeholder="Description (optional)"
				bind:value={description}
			></textarea>

			<!-- Status + Priority -->
			<div class="grid grid-cols-2 gap-3">
				<Select.Root type="single" bind:value={status}>
					<Select.Trigger class="w-full">
						<span class="inline-flex items-center gap-2">
							<StatusDot shape={statusShape(status)} color={STATUS_COLOR[status]} /> {STATUS_LABEL[status]}
						</span>
					</Select.Trigger>
					<Select.Content>
						{#each STATUS_ORDER as s (s)}
							<Select.Item value={s} label={STATUS_LABEL[s]} />
						{/each}
					</Select.Content>
				</Select.Root>
				<Select.Root type="single" value={priority || 'none'} onValueChange={(v) => (priority = v === 'none' ? '' : (v as TaskPriority))}>
					<Select.Trigger class="w-full">
						{#if priority}<Pills priority={priority} />{:else}<span class="text-gray-400">No priority</span>{/if}
					</Select.Trigger>
					<Select.Content>
						<Select.Item value="none" label="No priority" />
						{#each PRIORITY_ORDER as p (p)}
							<Select.Item value={p} label={p} />
						{/each}
					</Select.Content>
				</Select.Root>
			</div>

			<!-- Dates -->
			<div class="grid grid-cols-2 gap-3">
				<div class="space-y-1">
					<Label class="text-xs text-gray-500">Start date</Label>
					<input type="date" class="w-full text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded-md px-2 py-1.5" bind:value={start} />
				</div>
				<div class="space-y-1">
					<Label class="text-xs text-gray-500">Due date</Label>
					<input type="date" class="w-full text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded-md px-2 py-1.5" bind:value={due} />
				</div>
			</div>

			<!-- Tags (optional) — same picker as the task-detail Tags row, incl. create-new -->
			<div class="space-y-1">
				<Label class="text-xs text-gray-500">Tags</Label>
				<div class="flex flex-wrap items-center gap-1.5">
					{#each $labels.filter((l) => labelIds.includes(l.id)) as l (l.id)}
						<Pills label={l} size="md" />
					{/each}
					<DropdownMenu.Root>
						<DropdownMenu.Trigger class="inline-flex items-center justify-center gap-1 text-xs text-gray-400 rounded-md border border-dashed border-gray-300 dark:border-gray-700 hover:border-primary hover:text-primary {labelIds.length ? 'h-6 w-6 p-0' : 'h-6 px-1.5'}">
							<Icon name="plus" size={12} />{#if !labelIds.length}<span>Add tags</span>{/if}
						</DropdownMenu.Trigger>
						<DropdownMenu.Content class="w-64 p-0">
							<!-- Sticky top: search + always-present create button -->
							<div class="p-1.5 border-b border-gray-100 dark:border-gray-800">
								<input
									type="text"
									placeholder="Search or create a tag…"
									class="w-full text-sm rounded-md border border-gray-200 dark:border-gray-700 bg-transparent px-2 py-1 outline-none focus:border-primary"
									bind:value={labelQuery}
									onkeydown={onLabelSearchKey}
								/>
							</div>
							<button
								type="button"
								disabled={!labelQuery.trim() || creatingLabel}
								class="w-full flex items-center gap-2 px-2 py-1.5 text-sm text-primary hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed"
								onclick={createTagFromQuery}
							>
								<Icon name="plus" size={14} />
								<span class="truncate">
									{#if labelQuery.trim()}Create “{labelQuery.trim()}”{:else}Type a name to create a tag{/if}
								</span>
							</button>
							<div class="max-h-56 overflow-y-auto border-t border-gray-100 dark:border-gray-800 py-1">
								{#each filteredLabels as l (l.id)}
									<DropdownMenu.Item closeOnSelect={false} onSelect={() => toggleLabel(l.id)}>
										<span class="inline-flex items-center gap-2">
											<span class="w-3.5 inline-flex">{#if labelIds.includes(l.id)}<Icon name="check" size={13} />{/if}</span>
											<span class="w-2 h-2 rounded-full" style="background:{l.color}"></span>
											{l.name}
										</span>
									</DropdownMenu.Item>
								{/each}
								{#if $labels.length && !filteredLabels.length}
									<DropdownMenu.Item disabled>No matching tags</DropdownMenu.Item>
								{:else if !$labels.length}
									<DropdownMenu.Item disabled>No tags yet</DropdownMenu.Item>
								{/if}
							</div>
						</DropdownMenu.Content>
					</DropdownMenu.Root>
				</div>
			</div>

			<!-- Require attachment to complete -->
			<label class="flex items-start gap-2.5 rounded-lg border border-gray-200 dark:border-gray-800 px-3 py-2.5 cursor-pointer">
				<Checkbox
					checked={requireAttachment}
					onCheckedChange={(v) => (requireAttachment = !!v)}
					class="mt-0.5"
				/>
				<span class="text-sm">
					<span class="inline-flex items-center gap-1.5 font-medium"><Icon name="paperclip" size={14} /> Require attachment to complete</span>
					<span class="block text-xs text-gray-500 dark:text-gray-400 mt-0.5">The task can't be marked Done until a file is attached.</span>
				</span>
			</label>
		</div>

		<Dialog.Footer>
			<Button variant="outline" size="sm" onclick={close} disabled={busy}>Cancel</Button>
			<Button size="sm" onclick={submit} disabled={!canSubmit}>Create task</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
