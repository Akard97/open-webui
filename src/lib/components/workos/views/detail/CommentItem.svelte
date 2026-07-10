<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import Markdown from '$lib/components/chat/Messages/Markdown.svelte';
	import { Button } from '$lib/components/ui/button';
	import { user } from '$lib/stores';
	import { displayName, editComment, deleteCommentAction, roles, currentTeam } from '../../lib/store';
	import { renderMentions } from '../../lib/mentions';
	import { canDeleteComment } from '../../lib/roles';
	import type { Comment } from '../../lib/types';

	export let comment: Comment;

	$: myRole = $currentTeam ? $roles[$currentTeam.id] : undefined;
	$: rendered = renderMentions(comment.body, displayName);
	$: mine = comment.user_id === ($user?.id ?? '');

	let editing = false;
	let draft = '';
	function startEdit() { draft = comment.body; editing = true; }
	function save() { editComment(comment.id, draft); editing = false; }
</script>

<div class="py-2 group">
	<div class="flex items-center gap-2 mb-1">
		<span class="text-sm font-medium">{displayName(comment.user_id)}</span>
		{#if comment.edited_at}<span class="text-[11px] text-gray-400">(edited)</span>{/if}
		<div class="flex-1"></div>
		{#if mine}
			<Button variant="ghost" size="icon-xs" class="opacity-0 group-hover:opacity-100 text-gray-400" title="Edit" onclick={startEdit}><Icon name="pencil" size={13} /></Button>
		{/if}
		{#if canDeleteComment(comment, $user?.id ?? '', myRole)}
			<Button variant="destructive" size="icon-xs" class="opacity-0 group-hover:opacity-100" title="Delete" onclick={() => deleteCommentAction(comment.id)}><Icon name="trash" size={13} /></Button>
		{/if}
	</div>
	{#if editing}
		<textarea class="w-full text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded p-2 min-h-16" bind:value={draft}></textarea>
		<div class="flex gap-2 mt-1">
			<Button size="sm" onclick={save}>Save</Button>
			<Button variant="ghost" size="sm" onclick={() => (editing = false)}>Cancel</Button>
		</div>
	{:else}
		<div class="text-sm prose prose-sm dark:prose-invert max-w-none">
			<Markdown id={comment.id} content={rendered} />
		</div>
	{/if}
</div>
