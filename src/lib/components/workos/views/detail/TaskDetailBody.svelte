<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import Pills from '../../ui/Pills.svelte';
	import StatusDot from '../../ui/StatusDot.svelte';
	import PropertyRow from './PropertyRow.svelte';
	import DetailHeader from './DetailHeader.svelte';
	import AssigneeField from './AssigneeField.svelte';
	import AttachmentsPanel from './AttachmentsPanel.svelte';
	import SubtasksPanel from './SubtasksPanel.svelte';
	import { plannedProgress, actualProgress, taskHealth, HEALTH_LABEL, pointerToPercent, parsePercentInput } from '../../lib/progress';
	import CommentsPanel from './CommentsPanel.svelte';
	import ActivityItem from './ActivityItem.svelte';
	import * as Tabs from '$lib/components/ui/tabs';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { Badge } from '$lib/components/ui/badge';
	import {
		STATUS_ORDER, STATUS_LABEL, PRIORITY_ORDER, type TaskStatus, type TaskPriority
	} from '../../lib/types';
	import { formatDateLong } from '../../lib/format';
	import { selectedTask, closeTask, editTask, labels, comments, activity, createLabel, attachments, currentTeam } from '../../lib/store';
	import { STATUS_COLOR, statusShape } from '../../lib/colors';

	$: t = $selectedTask;
	$: commentCount = $comments.length;
	$: sortedActivity = [...$activity].sort((a, b) => a.created_at - b.created_at);
	$: needsAttachment = !!t?.attachment_required && $attachments.length === 0;
	$: foreignTeam = !!t && t.team_id !== ($currentTeam?.id ?? t.team_id);

	let showDetails = false;
	let editingTitle = false;
	let titleDraft = '';
	let editingStart = false;
	let editingDue = false;
	let barArmed = false;
	let dragValue: number | null = null;
	let dragging = false;
	let barEl: HTMLDivElement | null = null;
	let lastTaskId: string | null = null;
	let editingPercent = false;
	let percentDraft: string | number | null = '';
	let suppressPercentCommit = false;
	let focusSink: HTMLElement;
	let editingDesc = false;
	let descDraft = '';
	$: if (t && !editingDesc) descDraft = t.description ?? '';
	$: now = Date.now();
	$: actual = t ? actualProgress(t) : 0;
	$: planned = t ? plannedProgress(t.start_date, t.due_date, now) : null;
	$: health = t ? taskHealth(t, now) : null;
	// Color-code the actual progress bar by schedule health (green = good, red = overdue).
	$: actualBarColor =
		t?.status === 'done' ? 'bg-success'
		: t?.status === 'canceled' ? 'bg-gray-400'
		: health === 'overdue' ? 'bg-red-500'
		: health === 'behind' ? 'bg-orange-500'
		: health === 'at_risk' ? 'bg-amber-500'
		: health === 'on_track' ? 'bg-success'
		: 'bg-primary';

	$: editable = !!t && (t.subtask_total ?? 0) === 0;
	$: barValue = dragValue ?? actual;

	// Reset interaction state when switching tasks so an armed bar never leaks across tasks.
	$: if (t && t.id !== lastTaskId) {
		lastTaskId = t.id;
		barArmed = false;
		dragging = false;
		dragValue = null;
		editingPercent = false;
	}

	function setProgressFromEvent(e: PointerEvent) {
		if (!barEl) return;
		dragValue = pointerToPercent(e.clientX, barEl.getBoundingClientRect());
	}

	function commitDrag() {
		if (!t || dragValue === null) return;
		const v = dragValue;
		dragValue = null;
		if (v !== t.progress) editTask(t.id, { progress: v });
	}

	function onBarPointerDown(e: PointerEvent) {
		if (!editable) return;
		if (!barArmed) {
			barArmed = true; // first click only arms; does not change the value
			return;
		}
		dragging = true;
		(e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
		setProgressFromEvent(e);
	}

	function onBarPointerMove(e: PointerEvent) {
		if (dragging) setProgressFromEvent(e);
	}

	function onBarPointerUp(e: PointerEvent) {
		if (!dragging) return;
		dragging = false;
		(e.currentTarget as HTMLElement).releasePointerCapture?.(e.pointerId);
		commitDrag();
	}

	function onBarKeyDown(e: KeyboardEvent) {
		if (!editable || !t) return;
		if (e.key === 'Escape' || e.key === 'Enter') {
			barArmed = false;
			return;
		}
		if (!barArmed) {
			if (e.key === ' ' || e.key === 'Spacebar') {
				e.preventDefault();
				barArmed = true;
			}
			return;
		}
		if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
			e.preventDefault();
			const delta = e.key === 'ArrowRight' ? 1 : -1;
			const next = Math.max(0, Math.min(100, t.progress + delta));
			if (next !== t.progress) editTask(t.id, { progress: next });
		}
	}

	function onWindowPointerDown(e: PointerEvent) {
		if (barArmed && barEl && !barEl.contains(e.target as Node)) barArmed = false;
	}

	function focusSelect(node: HTMLInputElement) {
		node.focus();
		node.select();
	}

	function startPercentEdit() {
		if (!editable || !t) return;
		percentDraft = String(t.progress);
		suppressPercentCommit = false;
		editingPercent = true;
	}

	// Single commit funnel for every way the input loses focus (blur, Enter, Escape,
	// click-outside). Always closes the editor; only saves when not canceled.
	function commitPercent() {
		editingPercent = false;
		if (suppressPercentCommit) {
			suppressPercentCommit = false;
			return; // Escape: canceled, no save
		}
		if (!t) return;
		const v = parsePercentInput(percentDraft);
		if (v === null) return; // empty/invalid: revert, no save
		if (v !== t.progress) editTask(t.id, { progress: v });
	}

	// Enter/Escape redirect focus to an in-dialog sink BEFORE the input unmounts, so the
	// dialog's focus trap never reclaims focus to the header (it stays "on nothing").
	// The blur triggered by focusing the sink runs commitPercent via the input's onblur.
	function onPercentKey(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			focusSink?.focus();
		} else if (e.key === 'Escape') {
			e.preventDefault();
			// Keep Escape from reaching bits-ui's document-level escape layer, which
			// ignores defaultPrevented and would close the whole task dialog.
			e.stopPropagation();
			suppressPercentCommit = true;
			focusSink?.focus();
		}
	}

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

	// Tag picker search + create-new state.
	let labelQuery = '';
	$: filteredLabels = $labels.filter((l) =>
		l.name.toLowerCase().includes(labelQuery.trim().toLowerCase())
	);
	let creatingLabel = false;
	async function createTagFromQuery() {
		const name = labelQuery.trim();
		if (!name || creatingLabel) return;
		creatingLabel = true;
		try {
			const created = await createLabel(name);
			if (created && t) {
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
</script>

<svelte:window onpointerdown={onWindowPointerDown} />

{#if t}
	<div class="@container flex h-full min-h-0 flex-col overflow-hidden bg-white dark:bg-gray-950">
		<DetailHeader task={t} onEditTitle={startTitle} />

		<div class="flex flex-col @[880px]:flex-row flex-1 min-h-0 overflow-y-auto @[880px]:overflow-hidden">
			<!-- LEFT: title, properties, description -->
			<div class="w-full @[880px]:w-[440px] @[880px]:flex-none @[880px]:min-h-0 @[880px]:overflow-y-auto px-4 py-4 @[880px]:px-7 @[880px]:py-5 border-b @[880px]:border-b-0 @[880px]:border-r border-gray-200 dark:border-gray-800">
				<!-- Title -->
				{#if editingTitle}
					<!-- svelte-ignore a11y_autofocus -->
					<input
						class="w-full text-xl font-semibold bg-transparent mb-5 focus:outline-none border-b border-primary"
						bind:value={titleDraft}
						onblur={commitTitle}
						onkeydown={(e) => {
							if (e.key === 'Enter') commitTitle();
							if (e.key === 'Escape') {
								// stopPropagation: bits-ui's escape layer ignores defaultPrevented
								// and would close the dialog along with the inline edit.
								e.stopPropagation();
								editingTitle = false;
							}
						}}
						autofocus
					/>
				{:else}
					<button class="w-full text-left text-xl font-semibold mb-5 hover:opacity-80" onclick={startTitle}>
						{t.title}
					</button>
				{/if}

				<!-- Mobile: properties/description/attachments collapse behind one toggle -->
				<button
					class="@[880px]:hidden w-full flex items-center gap-2 rounded-lg border border-gray-200 dark:border-gray-800 px-3 py-2 text-sm font-medium mb-4"
					onclick={() => (showDetails = !showDetails)}
				>
					Details
					<span class="text-xs font-normal text-gray-400">status, dates, assignees…</span>
					<span class="flex-1"></span>
					<Icon name={showDetails ? 'chevron-up' : 'chevron-down'} size={14} />
				</button>
				<div class="{showDetails ? 'block' : 'hidden'} @[880px]:block">
				<!-- Properties -->
				<div class="space-y-1.5">
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
											{#if s === 'done' && needsAttachment}
												<span class="inline-flex items-center gap-1 text-[11px] text-amber-600 dark:text-amber-500">
													<Icon name="paperclip" size={12} /> attachment required
												</span>
											{/if}
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
								{#if t.priority}<Pills priority={t.priority} size="md" />{:else}<span class="text-gray-400">No priority</span>{/if}
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

					<!-- Start date -->
					<PropertyRow icon="calendar" label="Start date">
						{#if editingStart}
							<!-- svelte-ignore a11y_autofocus -->
							<input
								type="date"
								class="text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded px-2 py-1"
								value={t.start_date ? new Date(t.start_date).toISOString().slice(0, 10) : ''}
								onchange={(e) => {
									const v = (e.target as HTMLInputElement).value;
									editTask(t.id, { start_date: v ? new Date(v).getTime() : null });
									editingStart = false;
								}}
								onblur={() => (editingStart = false)}
								autofocus
							/>
						{:else}
							<button
								class="rounded-md px-1 -mx-1 py-0.5 hover:bg-gray-100 dark:hover:bg-gray-900 {t.start_date ? '' : 'text-gray-400'}"
								onclick={() => (editingStart = true)}
							>
								{t.start_date ? formatDateLong(t.start_date) : 'Add start date'}
							</button>
						{/if}
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
								<Pills label={l} size="md" />
							{/each}
							{#if !foreignTeam}
								<DropdownMenu.Root>
									<DropdownMenu.Trigger class="inline-flex items-center justify-center gap-1 text-xs text-gray-400 rounded-md border border-dashed border-gray-300 dark:border-gray-700 hover:border-primary hover:text-primary {t.labels.length ? 'h-6 w-6 p-0' : 'h-6 px-1.5'}">
										<Icon name="plus" size={12} />{#if !t.labels.length}<span>Add tags</span>{/if}
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
														<span class="w-3.5 inline-flex">{#if t.labels.includes(l.id)}<Icon name="check" size={13} />{/if}</span>
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
							{/if}
						</div>
					</PropertyRow>

					<!-- Progress -->
					<PropertyRow icon="loader" label="Progress" align="start">
						<div class="w-full space-y-2">
							<!-- Combined progress: planned (wide, behind) + actual (thin teal, on top), vertically centered -->
							<div class="flex items-center gap-2">
								<div
									bind:this={barEl}
									role={editable ? 'slider' : undefined}
									aria-valuenow={editable ? barValue : undefined}
									aria-valuemin={editable ? 0 : undefined}
									aria-valuemax={editable ? 100 : undefined}
									tabindex={editable ? 0 : undefined}
									class="relative flex-1 h-2.5 rounded-full bg-gray-100 dark:bg-gray-800 {barArmed ? 'overflow-visible ring-2 ring-primary/40' : 'overflow-hidden'} {editable ? 'cursor-pointer touch-none select-none' : ''}"
									onpointerdown={editable ? onBarPointerDown : undefined}
									onpointermove={editable ? onBarPointerMove : undefined}
									onpointerup={editable ? onBarPointerUp : undefined}
									onkeydown={editable ? onBarKeyDown : undefined}
								>
									{#if planned !== null}
										<div class="absolute inset-y-0 left-0 bg-gray-300 dark:bg-gray-600 rounded-full" style="width:{planned}%"></div>
									{/if}
									<div class="absolute left-0 top-1/2 -translate-y-1/2 h-1 {actualBarColor} rounded-full" style="width:{barValue}%"></div>
									{#if barArmed}
										<div class="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-white border-2 border-primary shadow" style="left:{barValue}%"></div>
									{/if}
								</div>
								{#if editingPercent}
									<input
										type="number"
										min="0"
										max="100"
										class="w-12 text-sm text-right rounded border border-brand-200 dark:border-brand-800 bg-transparent px-1 py-0.5 tabular-nums"
										bind:value={percentDraft}
										use:focusSelect
										onkeydown={onPercentKey}
										onblur={commitPercent}
									/>
								{:else}
									<button
										type="button"
										disabled={!editable}
										class="text-sm text-gray-500 w-10 text-right tabular-nums {editable ? 'cursor-text hover:text-primary' : 'cursor-default'}"
										onclick={startPercentEdit}
									>{barValue}%</button>
								{/if}
								<!-- Off-screen focus sink: receives focus when the percent input closes via Enter/Esc,
								     so the dialog's focus trap doesn't jump focus to the header. -->
								<span bind:this={focusSink} tabindex="-1" class="sr-only"></span>
							</div>
							{#if planned !== null}
								<div class="flex items-center gap-4 text-xs">
									<span class="inline-flex items-center gap-1.5 text-gray-600 dark:text-gray-300">
										<span class="inline-block w-2.5 h-1 rounded-full {actualBarColor}"></span>Actual {barValue}%
									</span>
									<span class="inline-flex items-center gap-1.5 text-gray-400">
										<span class="inline-block w-2.5 h-2.5 rounded-full bg-gray-300 dark:bg-gray-600"></span>Planned {planned}%
									</span>
								</div>
							{/if}
							{#if health}
								<span class="inline-flex text-xs rounded-full px-2 py-0.5 bg-gray-100 dark:bg-gray-900 text-gray-600 dark:text-gray-300">
									{HEALTH_LABEL[health]}
								</span>
							{/if}
							{#if (t.subtask_total ?? 0) === 0}
								{#if barArmed}
									<div class="text-xs text-gray-400">Click or drag the bar to set progress. Press Esc or Enter when done.</div>
								{/if}
							{:else}
								<div class="text-xs text-gray-400">{t.subtask_completed ?? 0}/{t.subtask_total ?? 0} subtasks complete</div>
							{/if}
						</div>
					</PropertyRow>
				</div>

				<!-- Description -->
				<div class="pt-3">
					<div class="flex items-center gap-2 text-[13px] font-medium text-gray-600 dark:text-gray-300 mb-2">
						<Icon name="align-left" size={15} /> Description
					</div>
					{#if editingDesc}
						<textarea class="w-full text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded-lg p-2.5 min-h-24" bind:value={descDraft}></textarea>
						<div class="flex gap-2 mt-2">
							<button class="text-sm px-3 py-1 rounded-md bg-primary text-primary-foreground" onclick={() => { editTask(t.id, { description: descDraft }); editingDesc = false; }}>Save</button>
							<button class="text-sm px-3 py-1 rounded-md border border-gray-300 dark:border-gray-700" onclick={() => (editingDesc = false)}>Cancel</button>
						</div>
					{:else}
						<button
							class="block w-full text-left text-sm whitespace-pre-wrap rounded-lg border border-gray-200 dark:border-gray-800 p-3 hover:border-gray-300 dark:hover:border-gray-700 {t.description ? 'text-black dark:text-white' : 'text-gray-400'}"
							onclick={() => (editingDesc = true)}
						>
							{t.description || 'Add a description…'}
						</button>
					{/if}
				</div>

				<!-- Attachments -->
				<AttachmentsPanel teamId={t.team_id} />
				</div>
			</div>

			<!-- RIGHT: tabs -->
			<div class="w-full @[880px]:flex-1 @[880px]:min-w-0 @[880px]:min-h-0 @[880px]:overflow-y-auto px-4 py-4 @[880px]:px-7 @[880px]:py-5">
				<!-- Tabs -->
				<div>
					<Tabs.Root value="comments">
						<Tabs.List variant="line" class="w-full justify-start gap-4 border-b border-gray-200 dark:border-gray-800 bg-transparent p-0">
							<Tabs.Trigger value="subtasks">Subtasks</Tabs.Trigger>
							<Tabs.Trigger value="comments" class="gap-1.5">
								Comments
								{#if commentCount}<Badge variant="secondary" class="px-1.5 py-0">{commentCount}</Badge>{/if}
							</Tabs.Trigger>
							<Tabs.Trigger value="activities">Activities</Tabs.Trigger>
						</Tabs.List>

						<Tabs.Content value="subtasks"><SubtasksPanel task={t} /></Tabs.Content>

						<Tabs.Content value="comments">
							<div class="@max-[880px]:pb-[env(safe-area-inset-bottom)]">
								<CommentsPanel taskId={t.id} teamId={t.team_id} />
							</div>
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
