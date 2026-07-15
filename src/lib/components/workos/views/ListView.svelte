<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import StatusDot from '../ui/StatusDot.svelte';
	import StatusBadge from '../ui/StatusBadge.svelte';
	import FilterBar from '../chrome/FilterBar.svelte';
	import AssigneeField from './detail/AssigneeField.svelte';
	import StatusCell from './cells/StatusCell.svelte';
	import PriorityCell from './cells/PriorityCell.svelte';
	import DueDateCell from './cells/DueDateCell.svelte';
	import ProgressCell from './cells/ProgressCell.svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { cn } from '$lib/components/ui/utils.js';
	import { Button, buttonVariants } from '$lib/components/ui/button';
	import { STATUS_ORDER, type TaskStatus } from '../lib/types';
	import { STATUS_COLOR, statusShape } from '../lib/colors';
	import { LIST_COLUMNS, gridTemplate } from '../lib/columns';
	import { canDeleteTask } from '../lib/roles';
	import { user, mobile } from '$lib/stores';
	import AssigneeAvatars from './AssigneeAvatars.svelte';
	import Pills from '../ui/Pills.svelte';
	import { formatDateShort, isOverdue } from '../lib/format';
	import {
		tasksByStatus, openTask, removeTask, openTaskCreate, directory, labels,
		boardFilter, listColumns, currentWorkstream, currentTeam, roles
	} from '../lib/store';

	$: byStatus = $tasksByStatus;
	$: void $directory; // re-render when names load
	$: labelById = Object.fromEntries($labels.map((l) => [l.id, l]));
	$: template = gridTemplate($listColumns);
	$: myRole = $currentTeam ? $roles[$currentTeam.id] : undefined;

	// Ephemeral UI state (not persisted): collapsed groups.
	let collapsed: Record<string, boolean> = {};

	function toggle(s: TaskStatus) {
		collapsed = { ...collapsed, [s]: !collapsed[s] };
	}
</script>

<div class="h-full flex flex-col min-h-0">
	<!-- Filters + Columns picker + Add new, all on one row (Columns/Add after the search). -->
	<FilterBar filter={boardFilter}>
		<DropdownMenu.Root>
			<DropdownMenu.Trigger class={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
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

		<Button size="sm" onclick={() => { const ws = $currentWorkstream; if (ws) openTaskCreate(ws.id); }}>
			<Icon name="plus" size={15} /> Add new
		</Button>
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
						<StatusBadge {status} size="md" />
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
												<span class="flex-none {isOverdue(task.due_date, task.status, Date.now()) ? 'text-red-600 dark:text-red-400 font-medium' : ''}">{formatDateShort(task.due_date)}</span>
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
							<Button variant="ghost" size="sm" class="text-primary"
								onclick={() => { const ws = $currentWorkstream; if (ws) openTaskCreate(ws.id, { status }); }}>
								<Icon name="plus" size={15} /> Add task
							</Button>
						</div>
					{/if}
				</section>
			{/if}
		{/each}
	</div>
</div>
