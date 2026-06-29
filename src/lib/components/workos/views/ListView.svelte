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
	import { user } from '$lib/stores';
	import {
		tasksByStatus, openTask, removeTask, addTask, directory, labels,
		boardFilter, listColumns, currentWorkstream, currentTeam, roles
	} from '../lib/store';

	$: byStatus = $tasksByStatus;
	$: void $directory; // re-render when names load
	$: labelById = Object.fromEntries($labels.map((l) => [l.id, l]));
	$: template = gridTemplate($listColumns);
	$: myRole = $currentTeam ? $roles[$currentTeam.id] : undefined;

	// Ephemeral UI state (not persisted): collapsed groups + per-group quick-add.
	let collapsed: Record<string, boolean> = {};
	let adding: TaskStatus | null = null;
	let newTitle = '';

	function toggle(s: TaskStatus) {
		collapsed = { ...collapsed, [s]: !collapsed[s] };
	}

	async function submitAdd(status: TaskStatus) {
		const ws = $currentWorkstream;
		if (!newTitle.trim() || !ws) return;
		await addTask(ws.id, { title: newTitle.trim(), status });
		newTitle = '';
		adding = null;
	}
</script>

<div class="h-full flex flex-col min-h-0">
	<FilterBar filter={boardFilter} />

	<!-- List toolbar: column picker (right-aligned) -->
	<div class="flex-none flex items-center justify-end px-4 py-2 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
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
	</div>

	<!-- Grouped, collapsible status sections -->
	<div class="flex-1 overflow-auto p-4 space-y-3">
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
						<!-- Column header -->
						<div class="grid items-center gap-3 px-3 py-1.5 border-t border-gray-100 dark:border-gray-900 text-xs text-gray-400" style="grid-template-columns: {template};">
							<!-- 26px aligns "Name" under the row title, past the StatusCell glyph: StatusDot(16) + gap-2.5(10) -->
							<span style="padding-left: 26px;">Name</span>
							{#if $listColumns.assignee}<span>Assignee</span>{/if}
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

						<!-- Add task — left pad = row px-3 (0.75rem) + 26px name offset (see header above) -->
						<div class="border-t border-gray-100 dark:border-gray-900 px-3 py-2" style="padding-left: calc(0.75rem + 26px);">
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
