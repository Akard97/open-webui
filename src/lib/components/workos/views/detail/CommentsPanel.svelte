<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { Badge } from '$lib/components/ui/badge';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import CommentThread from './CommentThread.svelte';
	import RichComposer from './RichComposer.svelte';
	import { comments, highlightCommentId } from '../../lib/store';
	import { buildCommentTree, type CommentSort } from '../../lib/commentTree';

	export let taskId: string;
	export let teamId: string | null = null;

	const PAGE = 10;
	let sort: CommentSort = 'newest';
	let shown = PAGE;
	let replyingToId: string | null = null;

	$: tree = buildCommentTree($comments, sort);
	$: visible = tree.slice(0, shown);
	$: hidden = tree.length - visible.length;

	// When a highlighted (deep-linked) comment sits beyond the pagination window
	// or in a hidden subtree, reveal everything so scrollIntoView can find it.
	$: if ($highlightCommentId && tree.length > shown) shown = tree.length;
</script>

<!-- ≥880px: header and composer are flex-none rails; only the thread list scrolls. -->
<div class="flex flex-col pt-3 @[880px]:min-h-0 @[880px]:flex-1">
	<div class="mb-1.5 flex flex-none items-center gap-2">
		<h3 class="text-[15px] font-bold">Comments</h3>
		{#if $comments.length}
			<Badge class="bg-primary px-2 py-0 text-white hover:bg-primary">{$comments.length}</Badge>
		{/if}
		<div class="flex-1"></div>
		<DropdownMenu.Root>
			<DropdownMenu.Trigger
				class="flex items-center gap-1 rounded-lg border border-gray-200 px-2.5 py-1 text-[12.5px] text-gray-500 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-900">
				<Icon name="arrow-up-down" size={12} />
				{sort === 'newest' ? 'Most recent' : 'Oldest first'}
				<Icon name="chevron-down" size={12} />
			</DropdownMenu.Trigger>
			<DropdownMenu.Content align="end">
				<DropdownMenu.Item onclick={() => (sort = 'newest')}>Most recent</DropdownMenu.Item>
				<DropdownMenu.Item onclick={() => (sort = 'oldest')}>Oldest first</DropdownMenu.Item>
			</DropdownMenu.Content>
		</DropdownMenu.Root>
	</div>

	<div class="@[880px]:min-h-0 @[880px]:flex-1 @[880px]:overflow-y-auto">
		{#if !tree.length}
			<p class="py-6 text-center text-[13px] text-gray-400">No comments yet — start the conversation.</p>
		{/if}

		{#each visible as node (node.comment.id)}
			<CommentThread
				{node} {taskId} {teamId}
				highlightId={$highlightCommentId}
				{replyingToId}
				onReply={(id) => (replyingToId = replyingToId === id ? null : id)}
				onCloseReply={() => (replyingToId = null)}
			/>
		{/each}

		{#if hidden > 0}
			<button
				class="mx-auto block py-2 text-[12.5px] font-bold text-primary hover:underline"
				onclick={() => (shown += PAGE)}
			>Show {Math.min(hidden, PAGE)} more ↓</button>
		{/if}
	</div>

	<div class="mt-3 flex-none border-t border-gray-200 bg-white pt-3 dark:border-gray-800 dark:bg-gray-950">
		<RichComposer {taskId} />
	</div>
</div>
