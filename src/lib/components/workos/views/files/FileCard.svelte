<script lang="ts">
	// Grid-mode gallery card: big preview (image thumb or tinted type glyph),
	// extension pill, hover actions, name + task-key/size meta.
	import Icon from '../../ui/Icon.svelte';
	import { attachmentUrl } from '../../lib/api';
	import { fileKind, isImage, formatBytes } from '../../lib/files';
	import { tint } from '../../lib/colors';
	import { openTask } from '../../lib/store';
	import type { WorkstreamFile } from '../../lib/types';

	export let file: WorkstreamFile;

	$: kind = fileKind(file.name, file.content_type);
</script>

<div
	class="group relative overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 transition-shadow hover:shadow-md hover:-translate-y-px"
>
	<!-- Preview -->
	<div class="relative h-28 grid place-items-center" style={isImage(file) ? '' : `background:${tint(kind.color, 9)}`}>
		{#if isImage(file)}
			<img src={attachmentUrl(file.id)} alt={file.name} loading="lazy" class="absolute inset-0 h-full w-full object-cover" />
		{:else}
			<span style="color:{kind.color}"><Icon name={kind.icon} size={30} /></span>
		{/if}
		<span
			class="absolute left-2 bottom-2 rounded-full px-2 py-0.5 text-[9.5px] font-bold tracking-wide text-white"
			style="background:{isImage(file) ? 'rgb(0 0 0 / 0.45)' : kind.color}"
		>{kind.ext}</span>
		<!-- Hover actions -->
		<span class="absolute right-2 top-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
			<a
				class="grid place-items-center size-7 rounded-md bg-white/90 dark:bg-gray-900/90 shadow-sm backdrop-blur text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
				href={attachmentUrl(file.id)}
				target="_blank"
				rel="noreferrer"
				title="Download"
			><Icon name="download" size={14} /></a>
			<button
				class="grid place-items-center size-7 rounded-md bg-white/90 dark:bg-gray-900/90 shadow-sm backdrop-blur text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
				onclick={() => openTask(file.task_id)}
				title="Open task"
			><Icon name="arrow-up-right" size={14} /></button>
		</span>
	</div>

	<!-- Body -->
	<div class="px-3 py-2.5">
		<a
			class="block text-xs font-medium truncate hover:text-primary"
			href={attachmentUrl(file.id)}
			target="_blank"
			rel="noreferrer"
			title={file.name}
		>{file.name}</a>
		<div class="mt-1 flex items-center gap-1.5 text-[11px] text-gray-400 min-w-0">
			<button class="font-semibold tabular-nums hover:text-primary flex-none" onclick={() => openTask(file.task_id)} title={file.task_title}>{file.task_key}</button>
			<span class="flex-1"></span>
			{#if file.comment_id}<Icon name="message-square" size={10} />{/if}
			<span class="tabular-nums">{formatBytes(file.size)}</span>
		</div>
	</div>
</div>
