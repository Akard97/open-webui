<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import CommentItem from './CommentItem.svelte';
	import RichComposer from './RichComposer.svelte';
	import { displayName } from '../../lib/store';
	import { countReplies, type CommentNode } from '../../lib/commentTree';

	export let node: CommentNode;
	export let taskId: string;
	export let teamId: string | null = null;
	export let highlightId: string | null = null;
	export let replyingToId: string | null = null;
	export let onReply: (commentId: string) => void;
	export let onCloseReply: () => void;
	// Author name of this node's parent comment, threaded down from the recursive
	// caller (a comment id can't be resolved via displayName — only user ids can).
	// The top-level caller in Task 8 omits it, so the root nodes get null.
	export let parentAuthorName: string | null = null;

	// Visual indent cap: depth 0-2 indent with rails; deeper children stay flat
	// with a "replying to" chip on each reply (see CommentItem replyToName).
	const INDENT_CAP = 3;

	let collapsed = false;
	$: replies = countReplies(node);
	$: indentKids = node.depth < INDENT_CAP - 1;
</script>

<CommentItem
	{node} {taskId} {teamId}
	highlight={node.comment.id === highlightId}
	replyToName={node.depth >= INDENT_CAP ? parentAuthorName : null}
	{onReply}
/>

{#if replyingToId === node.comment.id}
	<div class={indentKids ? 'ml-[15px] border-l-2 border-transparent pl-5' : ''}>
		<RichComposer
			{taskId} parentId={node.comment.id} compact autofocus
			placeholder="Write a reply…" submitLabel="Reply"
			onSubmitted={onCloseReply} onCancel={onCloseReply}
		/>
	</div>
{/if}

{#if node.children.length}
	<button
		class="ml-[42px] flex items-center gap-1.5 py-0.5 text-[12px] font-semibold text-primary"
		onclick={() => (collapsed = !collapsed)}
	>
		<Icon name={collapsed ? 'chevron-right' : 'chevron-down'} size={13} />
		{replies} {replies === 1 ? 'reply' : 'replies'}
	</button>
	{#if !collapsed}
		<div class={indentKids ? 'ml-[15px] border-l-2 border-gray-200 pl-5 @max-[880px]:ml-2 @max-[880px]:pl-3 dark:border-gray-800' : ''}>
			{#each node.children as child (child.comment.id)}
				<svelte:self
					node={child} {taskId} {teamId} {highlightId} {replyingToId} {onReply} {onCloseReply}
					parentAuthorName={displayName(node.comment.user_id)}
				/>
			{/each}
		</div>
	{/if}
{/if}
