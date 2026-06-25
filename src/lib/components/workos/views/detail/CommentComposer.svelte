<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { directory, postComment, uploadFiles } from '../../lib/store';
	import { mentionToken } from '../../lib/mentions';

	export let taskId: string;

	let body = '';
	let showMentions = false;
	let fileInput: HTMLInputElement;

	$: members = Object.entries($directory).map(([id, u]) => ({ id, name: u.name }));

	function insertMention(id: string, name: string) {
		body = `${body}${body.endsWith(' ') || body === '' ? '' : ' '}${mentionToken(id, name)} `;
		showMentions = false;
	}

	async function send() {
		const text = body.trim();
		if (!text) return;
		body = '';
		await postComment(taskId, text);
	}

	async function onFiles(e: Event) {
		const files = (e.target as HTMLInputElement).files;
		if (files && files.length) await uploadFiles(taskId, files);
		(e.target as HTMLInputElement).value = '';
	}
</script>

<div class="border-t border-gray-200 dark:border-gray-800 pt-2 mt-2">
	<textarea
		class="w-full text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded p-2 min-h-16"
		placeholder="Write a comment… use @ to mention"
		bind:value={body}
	></textarea>
	<div class="flex items-center gap-2 mt-1 relative">
		<button class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-900 text-gray-500" title="Mention" onclick={() => (showMentions = !showMentions)}><Icon name="users" size={15} /></button>
		<button class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-900 text-gray-500" title="Attach file" onclick={() => fileInput.click()}><Icon name="plus" size={15} /></button>
		<input type="file" multiple class="hidden" bind:this={fileInput} onchange={onFiles} />
		<div class="flex-1"></div>
		<button class="text-sm px-3 py-1 rounded bg-primary text-primary-foreground disabled:opacity-50" disabled={!body.trim()} onclick={send}>Comment</button>
		{#if showMentions}
			<div class="absolute bottom-9 left-0 z-10 w-56 max-h-48 overflow-y-auto rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-lg p-1">
				{#each members as m (m.id)}
					<button class="flex w-full px-2 h-8 items-center rounded text-sm hover:bg-gray-100 dark:hover:bg-gray-800" onclick={() => insertMention(m.id, m.name)}>{m.name}</button>
				{/each}
			</div>
		{/if}
	</div>
</div>
