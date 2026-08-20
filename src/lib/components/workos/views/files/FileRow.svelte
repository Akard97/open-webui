<script lang="ts">
	// One list row of the Files view. Columns must stay in lockstep with the
	// header template in FilesView.svelte.
	import Icon from '../../ui/Icon.svelte';
	import StatusDot from '../../ui/StatusDot.svelte';
	import { attachmentUrl } from '../../lib/api';
	import { fileKind, isImage, formatBytes, formatFileDate } from '../../lib/files';
	import { STATUS_COLOR, statusShape, tint } from '../../lib/colors';
	import { openTask, displayName, initials, directory } from '../../lib/store';
	import { avatarColors } from '../../lib/avatar';
	import { Avatar, AvatarFallback, AvatarImage } from '$lib/components/ui/avatar';
	import type { WorkstreamFile } from '../../lib/types';

	export let file: WorkstreamFile;
	export let now: number;

	$: kind = fileKind(file.name, file.content_type);
	$: av = avatarColors(file.created_by_id ?? '');
	$: uploaderImage = file.created_by_id ? ($directory[file.created_by_id]?.image ?? null) : null;
</script>

<div
	class="group grid items-center gap-3 px-3 py-2 border-t border-gray-100 dark:border-gray-900 hover:bg-gray-50 dark:hover:bg-gray-900/50 grid-cols-[minmax(0,1fr)_auto_auto] md:grid-cols-[minmax(0,1fr)_180px_90px_72px_84px] xl:grid-cols-[minmax(0,1fr)_220px_150px_90px_72px_84px]"
>
	<!-- Name: type tile / image thumb + filename + sub line -->
	<span class="flex items-center gap-3 min-w-0">
		{#if isImage(file)}
			<img
				src={attachmentUrl(file.id)}
				alt={file.name}
				loading="lazy"
				class="size-9 rounded-lg object-cover flex-none ring-1 ring-black/5 dark:ring-white/10"
			/>
		{:else}
			<span
				class="size-9 rounded-lg flex-none grid place-items-center"
				style="background:{tint(kind.color, 12)}; color:{kind.color}"
			>
				<Icon name={kind.icon} size={17} />
			</span>
		{/if}
		<span class="min-w-0">
			<a
				class="block text-sm font-medium truncate hover:text-primary"
				href={attachmentUrl(file.id)}
				target="_blank"
				rel="noreferrer"
				title={file.name}
			>{file.name}</a>
			<span class="flex items-center gap-1.5 text-[11px] text-gray-400">
				<span class="inline-flex items-center gap-1 md:hidden font-semibold tabular-nums">{file.task_key}</span>
				{#if file.comment_id}
					<span class="inline-flex items-center gap-1 rounded-full border border-gray-200 dark:border-gray-800 px-1.5 text-[10px] font-semibold text-gray-400">
						<Icon name="message-square" size={9} /> via comment
					</span>
				{/if}
			</span>
		</span>
	</span>

	<!-- Task chip (≥md) -->
	<button
		class="hidden md:inline-flex items-center gap-1.5 min-w-0 text-xs text-gray-500 dark:text-gray-400 hover:text-primary text-left"
		onclick={() => openTask(file.task_id)}
		title="{file.task_key} — {file.task_title}"
	>
		<StatusDot shape={statusShape(file.task_status)} color={STATUS_COLOR[file.task_status]} size={12} />
		<span class="font-semibold tabular-nums text-[11px] text-gray-400 flex-none">{file.task_key}</span>
		<span class="truncate">{file.task_title}</span>
	</button>

	<!-- Uploader (≥xl) -->
	<span class="hidden xl:flex items-center gap-2 min-w-0 text-xs text-gray-500 dark:text-gray-400">
		<Avatar class="size-[22px] flex-none">
			{#if uploaderImage}<AvatarImage src={uploaderImage} alt="" />{/if}
			<AvatarFallback
				class="text-[9px] font-bold"
				style="background:{av.background};color:{av.foreground}"
			>{initials(file.created_by_id)}</AvatarFallback>
		</Avatar>
		<span class="truncate">{displayName(file.created_by_id)}</span>
	</span>

	<!-- Added (≥md) -->
	<span class="hidden md:block text-xs text-gray-400 tabular-nums whitespace-nowrap">{formatFileDate(file.created_at, now)}</span>

	<!-- Size -->
	<span class="text-xs text-gray-400 tabular-nums whitespace-nowrap">{formatBytes(file.size)}</span>

	<!-- Actions: hover-reveal on desktop, always visible on touch widths -->
	<span class="flex items-center justify-end gap-0.5 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
		<a
			class="grid place-items-center size-7 rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-200/60 dark:hover:text-gray-200 dark:hover:bg-gray-800"
			href={attachmentUrl(file.id)}
			target="_blank"
			rel="noreferrer"
			title="Download"
		><Icon name="download" size={15} /></a>
		<button
			class="grid place-items-center size-7 rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-200/60 dark:hover:text-gray-200 dark:hover:bg-gray-800"
			onclick={() => openTask(file.task_id)}
			title="Open task"
		><Icon name="arrow-up-right" size={15} /></button>
	</span>
</div>
