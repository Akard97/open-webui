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
	import { openModal, addTask, directory, labels } from '../lib/store';

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
			requireAttachment = false;
			busy = false;
			err = '';
		}
	}

	function toDateInput(ts: number): string {
		return new Date(ts).toISOString().slice(0, 10);
	}

	$: members = Object.entries($directory).map(([id, u]) => ({ id, name: u.name }));
	$: labelById = Object.fromEntries($labels.map((l) => [l.id, l]));
	$: assigneeSummary =
		assigneeIds.length === 0 ? '' :
		assigneeIds.length === 1 ? ($directory[assigneeIds[0]]?.name ?? '1 assignee') :
		`${assigneeIds.length} assignees`;
	$: canSubmit = !!title.trim() && assigneeIds.length > 0 && !busy;

	function close() {
		openModal.set(null);
	}

	async function submit() {
		if (!req || !canSubmit) return;
		busy = true;
		err = '';
		try {
			await addTask(req.workstreamId, {
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
			close();
		} catch (e: any) {
			err = typeof e === 'string' ? e : (e?.detail ?? 'Could not create the task.');
		} finally {
			busy = false;
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

			<!-- Labels (optional) -->
			{#if $labels.length}
				<DropdownMenu.Root>
					<DropdownMenu.Trigger
						class="w-full inline-flex items-center gap-2 rounded-md border border-gray-200 dark:border-gray-800 px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-900"
					>
						<Icon name="tag" size={14} />
						{#if labelIds.length}
							<span>{labelIds.map((id) => labelById[id]?.name).filter(Boolean).join(', ')}</span>
						{:else}
							<span class="text-gray-400">Labels (optional)</span>
						{/if}
						<span class="flex-1"></span>
						<Icon name="chevron-down" size={13} />
					</DropdownMenu.Trigger>
					<DropdownMenu.Content class="w-64 max-h-64 overflow-y-auto">
						{#each $labels as l (l.id)}
							<DropdownMenu.CheckboxItem
								checked={labelIds.includes(l.id)}
								closeOnSelect={false}
								onCheckedChange={(v) => (labelIds = v ? [...labelIds, l.id] : labelIds.filter((x) => x !== l.id))}
							>
								<span class="inline-flex items-center gap-2">
									<span class="w-2 h-2 rounded-full" style="background:{l.color}"></span>{l.name}
								</span>
							</DropdownMenu.CheckboxItem>
						{/each}
					</DropdownMenu.Content>
				</DropdownMenu.Root>
			{/if}

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
			<Button variant="outline" size="sm" onclick={close}>Cancel</Button>
			<Button size="sm" onclick={submit} disabled={!canSubmit}>Create task</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
