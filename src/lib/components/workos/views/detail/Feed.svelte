<script lang="ts">
	import { feed } from '../../lib/store';
	import CommentItem from './CommentItem.svelte';
	import ActivityItem from './ActivityItem.svelte';
	import CommentComposer from './CommentComposer.svelte';

	export let taskId: string;
</script>

<div class="pt-4">
	<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-2">Activity</div>
	<div class="divide-y divide-gray-100 dark:divide-gray-900">
		{#each $feed as item (item.kind + (item.kind === 'comment' ? item.comment.id : item.activity.id))}
			{#if item.kind === 'comment'}
				<CommentItem comment={item.comment} />
			{:else}
				<ActivityItem activity={item.activity} />
			{/if}
		{/each}
	</div>
	<CommentComposer {taskId} />
</div>
