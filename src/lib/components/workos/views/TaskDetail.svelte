<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import Pills from '../ui/Pills.svelte';
	import { STATUS_ORDER, STATUS_LABEL, PRIORITY_ORDER, type TaskStatus, type TaskPriority } from '../lib/types';
	import { user } from '$lib/stores';
	import { canDeleteTask } from '../lib/roles';
	import {
		selectedTask, closeTask, editTask, removeTask, labels, directory, displayName, roles, currentTeam
	} from '../lib/store';
	import AttachmentList from './detail/AttachmentList.svelte';
	import Feed from './detail/Feed.svelte';

	$: t = $selectedTask;
	$: myRole = $currentTeam ? $roles[$currentTeam.id] : undefined;
	$: void $directory;

	let descDraft = '';
	let editingDesc = false;
	$: if (t && !editingDesc) descDraft = t.description ?? '';

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
			<div class="flex items-center gap-2 px-3 h-11 border-b border-gray-200 dark:border-gray-800">
				<span class="text-xs text-gray-400 font-mono">{t.key}</span>
				<div class="flex-1"></div>
				{#if canDeleteTask(t, $user?.id ?? '', myRole)}
					<button class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-900 text-red-500" title="Delete" onclick={() => removeTask(t.id)}>
						<Icon name="trash" size={15} />
					</button>
				{/if}
				<button class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-900" onclick={closeTask}><Icon name="x" size={16} /></button>
			</div>

			<div class="flex-1 overflow-y-auto p-4">
				<input
					class="w-full text-lg font-semibold bg-transparent mb-4 focus:outline-none"
					value={t.title}
					onchange={(e) => editTask(t.id, { title: (e.target as HTMLInputElement).value })}
				/>

				<div class="space-y-2.5 pb-4 border-b border-gray-200 dark:border-gray-800">
					<div class="flex items-center min-h-8">
						<span class="w-24 text-sm text-gray-400">Status</span>
						<select class="text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded px-2 py-1" value={t.status} onchange={(e) => editTask(t.id, { status: (e.target as HTMLSelectElement).value as TaskStatus })}>
							{#each STATUS_ORDER as s (s)}<option value={s}>{STATUS_LABEL[s]}</option>{/each}
							<option value="canceled">Canceled</option>
						</select>
					</div>
					<div class="flex items-center min-h-8">
						<span class="w-24 text-sm text-gray-400">Priority</span>
						<select class="text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded px-2 py-1" value={t.priority ?? ''} onchange={(e) => { const v = (e.target as HTMLSelectElement).value; editTask(t.id, { priority: (v || null) as TaskPriority | null }); }}>
							<option value="">No priority</option>
							{#each PRIORITY_ORDER as p (p)}<option value={p}>{p}</option>{/each}
						</select>
					</div>
					<div class="flex items-center min-h-8">
						<span class="w-24 text-sm text-gray-400">Assignee</span>
						<select class="text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded px-2 py-1" value={t.assignee_id ?? ''} onchange={(e) => { const v = (e.target as HTMLSelectElement).value; editTask(t.id, { assignee_id: v || null }); }}>
							<option value="">Unassigned</option>
							{#each Object.entries($directory) as [id, u] (id)}<option value={id}>{u.name}</option>{/each}
						</select>
					</div>
					<div class="flex items-center min-h-8">
						<span class="w-24 text-sm text-gray-400">Due date</span>
						<input
							type="date"
							class="text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded px-2 py-1"
							value={t.due_date ? new Date(t.due_date).toISOString().slice(0, 10) : ''}
							onchange={(e) => { const v = (e.target as HTMLInputElement).value; editTask(t.id, { due_date: v ? new Date(v).getTime() : null }); }}
						/>
					</div>
					<div class="flex items-start min-h-8">
						<span class="w-24 text-sm text-gray-400 pt-1">Labels</span>
						<div class="flex flex-wrap gap-1.5">
							{#each $labels as l (l.id)}
								<button class="text-[11px] px-1.5 py-0.5 rounded border {t.labels.includes(l.id) ? 'border-teal-500 bg-teal-50 dark:bg-teal-900/30' : 'border-gray-200 dark:border-gray-700'}" onclick={() => toggleLabel(l.id)}>
									<Pills label={l} />
								</button>
							{/each}
						</div>
					</div>
					<div class="flex items-center min-h-8">
						<span class="w-24 text-sm text-gray-400">Progress</span>
						<input type="range" min="0" max="100" step="5" value={t.progress} onchange={(e) => editTask(t.id, { progress: parseInt((e.target as HTMLInputElement).value, 10) })} />
						<span class="ml-2 text-sm">{t.progress}%</span>
					</div>
				</div>

				<div class="pt-4">
					<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-2">Description</div>
					{#if editingDesc}
						<textarea class="w-full text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded p-2 min-h-24" bind:value={descDraft}></textarea>
						<div class="flex gap-2 mt-2">
							<button class="text-sm px-3 py-1 rounded bg-teal-600 text-white" onclick={() => { editTask(t.id, { description: descDraft }); editingDesc = false; }}>Save</button>
							<button class="text-sm px-3 py-1 rounded border border-gray-300 dark:border-gray-700" onclick={() => (editingDesc = false)}>Cancel</button>
						</div>
					{:else}
						<button class="text-sm text-left text-gray-600 dark:text-gray-300 whitespace-pre-wrap w-full" onclick={() => (editingDesc = true)}>
							{t.description || 'Add a description…'}
						</button>
					{/if}
				</div>

				<AttachmentList />
				<Feed taskId={t.id} />
			</div>
		</div>
	</div>
{/if}
