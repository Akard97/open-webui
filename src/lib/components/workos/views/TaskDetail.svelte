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
	<div class="fixed inset-0 z-[70] flex justify-end">
		<div class="absolute inset-0 bg-black/30" onclick={closeTask} role="presentation"></div>
		<div class="relative w-[700px] max-w-[92%] h-full bg-white dark:bg-gray-950 border-l border-gray-200 dark:border-gray-800 shadow-xl flex flex-col">
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
								<DropdownMenu.Trigger class="inline-flex items-center gap-1 text-xs text-gray-400 rounded-md px-1.5 py-0.5 border border-dashed border-gray-300 dark:border-gray-700 hover:border-teal-500 hover:text-teal-600 dark:hover:text-teal-400">
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
								<button class="text-xs text-teal-600 dark:text-teal-400" onclick={() => (editingProgress = false)}>Done</button>
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
