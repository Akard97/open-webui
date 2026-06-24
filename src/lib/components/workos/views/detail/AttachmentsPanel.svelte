<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import * as Card from '$lib/components/ui/card';
	import {
		attachments,
		removeAttachment,
		uploadFiles,
		roles,
		currentTeam,
		selectedTaskId
	} from '../../lib/store';
	import { user } from '$lib/stores';
	import { canDeleteAttachment } from '../../lib/roles';
	import * as api from '../../lib/api';

	$: myRole = $currentTeam ? $roles[$currentTeam.id] : undefined;
	$: files = $attachments.filter((a) => !a.comment_id);

	const isImage = (ct?: string | null) => !!ct && ct.startsWith('image/');
	const kb = (n: number) => `${Math.max(1, Math.round(n / 1024))} KB`;

	let fileInput: HTMLInputElement;

	function downloadAll() {
		for (const a of files) {
			const link = document.createElement('a');
			link.href = api.attachmentUrl(a.id);
			link.download = a.name;
			link.target = '_blank';
			document.body.appendChild(link);
			link.click();
			link.remove();
		}
	}

	async function onFiles(e: Event) {
		const fl = (e.target as HTMLInputElement).files;
		const taskId = $selectedTaskId;
		if (fl && fl.length && taskId) await uploadFiles(taskId, fl);
		(e.target as HTMLInputElement).value = '';
	}
</script>

<div class="pt-4">
	<div class="flex items-center justify-between mb-2">
		<div class="flex items-center gap-2 text-[13px] font-medium text-gray-600 dark:text-gray-300">
			<Icon name="paperclip" size={15} /> Attachments ({files.length})
		</div>
		{#if files.length}
			<button
				class="inline-flex items-center gap-1 text-xs text-teal-600 hover:text-teal-700 dark:text-teal-400 dark:hover:text-teal-300"
				onclick={downloadAll}
			>
				<Icon name="download" size={13} /> Download All
			</button>
		{/if}
	</div>

	<div class="grid grid-cols-2 gap-2">
		{#each files as a (a.id)}
			<Card.Root class="p-2.5 flex flex-row items-center gap-2 group rounded-xl">
				{#if isImage(a.content_type)}
					<img src={api.attachmentUrl(a.id)} alt={a.name} class="w-9 h-9 rounded object-cover flex-none" />
				{:else}
					<span class="w-9 h-9 rounded bg-gray-100 dark:bg-gray-800 flex items-center justify-center flex-none text-gray-500">
						<Icon name="file" size={18} />
					</span>
				{/if}
				<div class="min-w-0 flex-1">
					<div class="text-xs font-medium truncate">{a.name}</div>
					<div class="text-[11px] text-gray-400 flex items-center gap-1">
						{kb(a.size)} ·
						<a class="text-teal-600 dark:text-teal-400 hover:underline" href={api.attachmentUrl(a.id)} target="_blank" rel="noreferrer">Download</a>
					</div>
				</div>
				{#if canDeleteAttachment(a, $user?.id ?? '', myRole)}
					<button class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 flex-none" title="Remove" onclick={() => removeAttachment(a.id)}>
						<Icon name="trash" size={13} />
					</button>
				{/if}
			</Card.Root>
		{/each}
		<button
			class="flex items-center justify-center rounded-xl border border-dashed border-gray-300 dark:border-gray-700 text-gray-400 hover:border-teal-500 hover:text-teal-600 min-h-[64px]"
			onclick={() => fileInput.click()}
			title="Add attachment"
		>
			<Icon name="plus" size={18} />
		</button>
	</div>

	<input type="file" multiple class="hidden" bind:this={fileInput} onchange={onFiles} />
</div>
