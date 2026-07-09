<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import StatusDot from '../ui/StatusDot.svelte';
	import FilterBar from '../chrome/FilterBar.svelte';
	import AssigneeField from './detail/AssigneeField.svelte';
	import StatusCell from './cells/StatusCell.svelte';
	import PriorityCell from './cells/PriorityCell.svelte';
	import DueDateCell from './cells/DueDateCell.svelte';
	import ProgressCell from './cells/ProgressCell.svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { cn } from '$lib/components/ui/utils.js';
	import { buttonVariants } from '$lib/components/ui/button';
	import { STATUS_ORDER, STATUS_LABEL, type TaskStatus } from '../lib/types';
	import { STATUS_COLOR, statusShape } from '../lib/colors';
	import { LIST_COLUMNS, gridTemplate } from '../lib/columns';
	import { canDeleteTask } from '../lib/roles';
	import { user, mobile } from '$lib/stores';
	import AssigneeAvatars from './AssigneeAvatars.svelte';
	import Pills from '../ui/Pills.svelte';
	import { isOverdue } from '../lib/calendar';
	import { formatDateShort } from '../lib/format';
	import { toast } from 'svelte-sonner';
	import {
		tasksByStatus, openTask, removeTask, addTask, directory, labels,
		boardFilter, listColumns, currentWorkstream, currentTeam, roles
	} from '../lib/store';

	$: byStatus = $tasksByStatus;
	$: void $directory; // re-render when names load
	$: labelById = Object.fromEntries($labels.map((l) => [l.id, l]));
	$: template = gridTemplate($listColumns);
	$: myRole = $currentTeam ? $roles[$currentTeam.id] : undefined;

	// Ephemeral UI state (not persisted): collapsed groups + per-group quick-add +
	// the toolbar "Add new" quick-add.
	let collapsed: Record<string, boolean> = {};
	let adding: TaskStatus | null = null;
	let newTitle = '';
	let creatingNew = false;
	let newGlobalTitle = '';

	function toggle(s: TaskStatus) {
		collapsed = { ...collapsed, [s]: !collapsed[s] };
	}

	async function submitAdd(status: TaskStatus) {
		const ws = $currentWorkstream;
		const t = newTitle.trim();
		if (!t || !ws) return;
		newTitle = '';
		adding = null;
		try {
			await addTask(ws.id, { title: t, status });
		} catch {
			toast.error('Failed to create task');
			// Give the title back — unless the user already started another entry.
			if (adding === null && !newTitle) {
				adding = status;
				newTitle = t;
			}
		}
	}

	// Toolbar "Add new" — creates a task in the default (backlog) status, like the
	// old Topbar entry point it replaces.
	async function submitNew() {
		const ws = $currentWorkstream;
		const t = newGlobalTitle.trim();
		if (!t || !ws) return;
		newGlobalTitle = '';
		creatingNew = false;
		try {
			await addTask(ws.id, { title: t });
		} catch {
			toast.error('Failed to create task');
			if (!creatingNew && !newGlobalTitle) {
				creatingNew = true;
				newGlobalTitle = t;
			}
		}
	}
</script>

<div class="h-full flex flex-col min-h-0">
	<!-- Filters + Columns picker + Add new, all on one row (Columns/Add after the search). -->
	<FilterBar filter={boardFilter}>
		<DropdownMenu.Root>
			<DropdownMenu.Trigger class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 text-sm hover:bg-gray-100 dark:hover:bg-gray-900">
				<Icon name="sliders" size={14} /> Columns <Icon name="chevron-down" size={13} />
			</DropdownMenu.Trigger>
			<DropdownMenu.Content align="end">
				{#each LIST_COLUMNS as c (c.key)}
					<DropdownMenu.CheckboxItem
						checked={$listColumns[c.key]}
						closeOnSelect={false}
						onCheckedChange={(v) => listColumns.update((p) => ({ ...p, [c.key]: !!v }))}
					>{c.label}</DropdownMenu.CheckboxItem>
				{/each}
			</DropdownMenu.Content>
		</DropdownMenu.Root>

		{#if creatingNew}
			<!-- svelte-ignore a11y_autofocus -->
			<input
				class="text-sm px-2 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent w-48"
				placeholder="Task title…"
				bind:value={newGlobalTitle}
				onkeydown={(e) => { if (e.key === 'Enter') submitNew(); if (e.key === 'Escape') { creatingNew = false; newGlobalTitle = ''; } }}
				autofocus
			/>
		{:else}
			<button class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground text-sm font-medium" onclick={() => { creatingNew = true; newGlobalTitle = ''; }}>
				<Icon name="plus" size={15} /> Add new
			</button>
		{/if}
	</FilterBar>

	<!-- Grouped, collapsible status sections -->
	<div class="flex-1 overflow-auto p-4 space-y-3 bg-white dark:bg-gray-900">
		{#each STATUS_ORDER as status (status)}
			{#if (byStatus[status] ?? []).length}
				<section class="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 overflow-hidden">
					<!-- Group header -->
					<div class="flex items-center gap-2 px-3 py-2.5">
						<button class="text-gray-400 hover:text-gray-600" onclick={() => toggle(status)} title={collapsed[status] ? 'Expand' : 'Collapse'}>
							<Icon name={collapsed[status] ? 'chevron-right' : 'chevron-down'} size={16} />
						</button>
						<span
							class="inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-[13px] font-medium"
							style="background:{STATUS_COLOR[status]}24; color:{STATUS_COLOR[status]}"
						>
							<StatusDot shape={statusShape(status)} color={STATUS_COLOR[status]} size={14} />
							{STATUS_LABEL[status]}
						</span>
						<span class="text-xs text-gray-400">{byStatus[status].length}</span>
					</div>

					{#if !collapsed[status]}
						{#if !$mobile}
							<!-- Column header -->
							<div class="grid items-center gap-3 px-3 py-1.5 border-t border-gray-100 dark:border-gray-900 text-xs text-gray-400" style="grid-template-columns: {template};">
								<!-- 26px aligns "Name" under the row title, past the StatusCell glyph: StatusDot(16) + gap-2.5(10) -->
								<span style="padding-left: 26px;">Name</span>
								{#if $listColumns.assignee}<span>Assignee</span>{/if}
								{#if $listColumns.start}<span>Start date</span>{/if}
								{#if $listColumns.due}<span>Due date</span>{/if}
								{#if $listColumns.priority}<span>Priority</span>{/if}
								{#if $listColumns.labels}<span>Labels</span>{/if}
								{#if $listColumns.progress}<span>Progress</span>{/if}
								<span></span>
							</div>

							<!-- Task rows -->
							{#each byStatus[status] as task (task.id)}
								<div class="group grid items-center gap-3 px-3 py-2 border-t border-gray-100 dark:border-gray-900 hover:bg-gray-50 dark:hover:bg-gray-900/50" style="grid-template-columns: {template};">
									<!-- Name (status circle + title) -->
									<span class="inline-flex items-center gap-2.5 min-w-0">
										<StatusCell {task} />
										<button class="text-sm font-medium truncate text-left hover:text-primary" onclick={() => openTask(task.id)}>{task.title}</button>
									</span>

									{#if $listColumns.assignee}
										<span class="min-w-0"><AssigneeField {task} placeholder="Assign" /></span>
									{/if}
									{#if $listColumns.start}
										<span class="min-w-0"><DueDateCell {task} field="start_date" /></span>
									{/if}
									{#if $listColumns.due}
										<span class="min-w-0"><DueDateCell {task} /></span>
									{/if}
									{#if $listColumns.priority}
										<span class="min-w-0"><PriorityCell {task} /></span>
									{/if}
									{#if $listColumns.labels}
										<span class="flex items-center gap-1 min-w-0 overflow-hidden">
											{#each (task.labels ?? []).slice(0, 2) as lid (lid)}
												{#if labelById[lid]}
													<span class="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 whitespace-nowrap">
														<span class="w-1.5 h-1.5 rounded-full" style="background:{labelById[lid].color}"></span>{labelById[lid].name}
													</span>
												{/if}
											{/each}
											{#if (task.labels?.length ?? 0) > 2}
												<span class="text-[11px] text-gray-400">+{(task.labels?.length ?? 0) - 2}</span>
											{:else if !(task.labels?.length)}
												<span class="text-gray-300 dark:text-gray-600">—</span>
											{/if}
										</span>
									{/if}
									{#if $listColumns.progress}
										<span class="min-w-0"><ProgressCell {task} /></span>
									{/if}

									<!-- Row menu -->
									<DropdownMenu.Root>
										<DropdownMenu.Trigger
											title="More"
											class={cn(buttonVariants({ variant: 'ghost', size: 'icon-sm' }), 'opacity-0 group-hover:opacity-100 text-gray-400 hover:text-gray-600')}
										>
											<Icon name="more-horizontal" size={16} />
										</DropdownMenu.Trigger>
										<DropdownMenu.Content align="end">
											<DropdownMenu.Item onSelect={() => openTask(task.id)}>
												<span class="inline-flex items-center gap-2"><Icon name="pencil" size={14} /> Edit</span>
											</DropdownMenu.Item>
											{#if canDeleteTask(task, $user?.id ?? '', myRole)}
												<DropdownMenu.Item class="text-red-600" onSelect={() => removeTask(task.id)}>
													<span class="inline-flex items-center gap-2"><Icon name="trash" size={14} /> Delete</span>
												</DropdownMenu.Item>
											{/if}
										</DropdownMenu.Content>
									</DropdownMenu.Root>
								</div>
							{/each}
						{:else}
							{#each byStatus[status] as task (task.id)}
								<button
									class="w-full flex items-start gap-2.5 px-3 py-2.5 border-t border-gray-100 dark:border-gray-900 text-left active:bg-gray-50 dark:active:bg-gray-900/50"
									onclick={() => openTask(task.id)}
								>
									<span class="mt-0.5 flex-none"><StatusDot shape={statusShape(task.status)} color={STATUS_COLOR[task.status]} size={16} /></span>
									<span class="flex-1 min-w-0">
										<span class="block text-sm font-medium truncate">{task.title}</span>
										<span class="mt-1 flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
											<span class="flex-none">{task.key}</span>
											{#if task.due_date != null}
												<span class="flex-none {isOverdue(task, Date.now()) ? 'text-red-600 dark:text-red-400 font-medium' : ''}">{formatDateShort(task.due_date)}</span>
											{/if}
											{#if task.priority}<Pills priority={task.priority} />{/if}
										</span>
									</span>
									{#if task.assignee_ids?.length}
										<span class="flex-none mt-0.5"><AssigneeAvatars ids={task.assignee_ids} max={3} size={20} /></span>
									{/if}
								</button>
							{/each}
						{/if}

						<!-- Add task — left pad = row px-3 (0.75rem) + 26px name offset (see header above) -->
						<div class="border-t border-gray-100 dark:border-gray-900 px-3 py-2 md:pl-[calc(0.75rem+26px)]">
							{#if adding === status}
								<!-- svelte-ignore a11y_autofocus -->
								<input
									class="text-sm px-2 py-1 rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent w-64"
									placeholder="Task title…"
									bind:value={newTitle}
									onkeydown={(e) => { if (e.key === 'Enter') submitAdd(status); if (e.key === 'Escape') { adding = null; newTitle = ''; } }}
									autofocus
								/>
							{:else}
								<button class="inline-flex items-center gap-1.5 text-sm text-primary font-medium hover:opacity-80" onclick={() => { adding = status; newTitle = ''; }}>
									<Icon name="plus" size={15} /> Add task
								</button>
							{/if}
						</div>
					{/if}
				</section>
			{/if}
		{/each}
	</div>
</div>
