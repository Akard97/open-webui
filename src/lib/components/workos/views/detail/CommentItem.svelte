<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import Markdown from '$lib/components/chat/Messages/Markdown.svelte';
	import { Button } from '$lib/components/ui/button';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { user } from '$lib/stores';
	import {
		displayName, deleteCommentAction, toggleReactionAction, roles, currentTeam, attachments,
		directory
	} from '../../lib/store';
	import { Avatar, AvatarFallback, AvatarImage } from '$lib/components/ui/avatar';
	import { renderMentions } from '../../lib/mentions';
	import { agoLong } from '../../lib/inboxFormat';
	import { avatarColors } from '../../lib/avatar';
	import { canDeleteComment } from '../../lib/roles';
	import { attachmentUrl } from '../../lib/api';
	import type { CommentNode } from '../../lib/commentTree';
	import RichComposer from './RichComposer.svelte';
	import ImageLightbox from './ImageLightbox.svelte';

	export let node: CommentNode;
	export let taskId: string;
	export let teamId: string | null = null;
	export let highlight = false;
	export let replyToName: string | null = null;
	export let onReply: (commentId: string) => void;

	const EMOJI = ['👍', '❤️', '🎉', '👀', '😂', '🚀'];

	$: comment = node.comment;
	$: tombstoned = !!comment.deleted_at;
	$: myRole = teamId ? $roles[teamId] : $currentTeam ? $roles[$currentTeam.id] : undefined;
	$: rendered = renderMentions(comment.body, displayName);
	$: mine = comment.user_id === ($user?.id ?? '');
	$: colors = avatarColors(comment.user_id);
	$: initials = displayName(comment.user_id).slice(0, 2).toUpperCase();
	$: image = tombstoned ? null : ($directory[comment.user_id]?.image ?? null);
	$: images = $attachments.filter(
		(a) => a.comment_id === comment.id && (a.content_type ?? '').startsWith('image/')
	);
	$: reactions = comment.reactions ?? [];
	$: myId = $user?.id ?? '';

	let rootEl: HTMLElement | null = null;
	$: if (highlight && rootEl) rootEl.scrollIntoView({ block: 'center', behavior: 'smooth' });

	let editing = false;
	let pickerOpen = false;
	let lightboxSrc: string | null = null;
	let lightboxAlt = '';

	function interceptMentionClick(e: MouseEvent): void {
		const a = (e.target as HTMLElement).closest?.('a[href^="#mention-"]');
		if (a) e.preventDefault(); // mention chips are labels, not links
	}
</script>

<div bind:this={rootEl}
	class="group flex gap-2.5 py-2.5 {highlight ? 'rounded-lg bg-primary/5 px-2 ring-1 ring-primary/20' : ''}">
	<Avatar class="flex-none {node.depth === 0 ? 'size-8' : 'size-[26px]'}">
		{#if image}<AvatarImage src={image} alt="" />{/if}
		<AvatarFallback class="font-bold {node.depth === 0 ? 'text-[12px]' : 'text-[10px]'}"
			style="background:{tombstoned ? 'rgb(156 163 175)' : colors.background};color:{tombstoned ? '#fff' : colors.foreground}">
			{tombstoned ? '?' : initials}
		</AvatarFallback>
	</Avatar>

	<div class="min-w-0 flex-1">
		{#if replyToName}
			<span class="mb-0.5 inline-flex items-center gap-1 rounded-md bg-primary/10 px-1.5 py-px text-[11px] font-medium text-primary">
				<Icon name="corner-up-left" size={11} /> replying to @{replyToName}
			</span>
		{/if}

		{#if tombstoned}
			<div class="flex items-baseline gap-2">
				<span class="text-[13px] font-semibold text-gray-400">Comment deleted</span>
				<span class="text-[11px] tabular-nums text-gray-400">{agoLong(comment.created_at)}</span>
			</div>
			<div class="mt-1 rounded-lg bg-gray-100 px-2.5 py-1.5 text-[13px] italic text-gray-400 dark:bg-gray-900">
				This comment was deleted.
			</div>
		{:else}
			<div class="flex items-baseline gap-2">
				<span class="text-[13.5px] font-semibold">{displayName(comment.user_id)}</span>
				<span class="text-[11px] tabular-nums text-gray-400">{agoLong(comment.created_at)}</span>
				{#if comment.edited_at}<span class="text-[10.5px] italic text-gray-400">(edited)</span>{/if}
			</div>

			{#if editing}
				<div class="mt-1">
					<RichComposer
						{taskId} mode="edit" commentId={comment.id} compact allowImages={false}
						initialBody={comment.body} submitLabel="Save" autofocus
						onSubmitted={() => (editing = false)} onCancel={() => (editing = false)}
					/>
				</div>
			{:else}
				<!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
				<div class="wos-comment-prose prose prose-sm mt-0.5 max-w-none text-[13.5px] dark:prose-invert"
					onclick={interceptMentionClick}>
					<Markdown id={comment.id} content={rendered} />
				</div>

				{#if images.length}
					<div class="mt-1.5 flex flex-wrap gap-2">
						{#each images as img (img.id)}
							<button
								class="h-[68px] w-24 overflow-hidden rounded-lg border border-gray-200 dark:border-gray-800"
								title="Click to expand"
								onclick={() => { lightboxSrc = attachmentUrl(img.id); lightboxAlt = img.name; }}
							>
								<img src={attachmentUrl(img.id)} alt={img.name} class="size-full cursor-zoom-in object-cover" />
							</button>
						{/each}
					</div>
				{/if}

				<div class="mt-1.5 flex items-center gap-1.5">
					{#each reactions as r (r.emoji)}
						<button
							class="flex items-center gap-1 rounded-full border px-2 py-px text-[12px] transition-colors
								{r.user_ids.includes(myId)
									? 'border-primary bg-primary/10 font-semibold text-primary'
									: 'border-gray-200 hover:border-gray-300 dark:border-gray-800 dark:hover:border-gray-700'}"
							title={r.user_ids.map((id) => displayName(id)).join(', ')}
							onclick={() => void toggleReactionAction(comment.id, r.emoji)}
						>{r.emoji} {r.count}</button>
					{/each}

					<div class="relative">
						<button
							class="flex items-center rounded-full border border-dashed border-gray-200 px-1.5 py-px text-gray-400 hover:border-gray-300 hover:text-gray-500 dark:border-gray-800"
							title="Add reaction" onclick={() => (pickerOpen = !pickerOpen)}
						><Icon name="smile-plus" size={13} /></button>
						{#if pickerOpen}
							<div class="absolute bottom-6 left-0 z-10 flex gap-0.5 rounded-full border border-gray-200 bg-white px-1.5 py-1 shadow-lg dark:border-gray-800 dark:bg-gray-900">
								{#each EMOJI as e (e)}
									<button class="rounded-md px-1 text-[15px] hover:bg-gray-100 dark:hover:bg-gray-800"
										onclick={() => { pickerOpen = false; void toggleReactionAction(comment.id, e); }}
									>{e}</button>
								{/each}
							</div>
						{/if}
					</div>

					<button class="rounded-md px-1.5 py-px text-[12px] font-semibold text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
						onclick={() => onReply(comment.id)}>Reply</button>

					<div class="flex-1"></div>

					{#if mine || canDeleteComment(comment, myId, myRole)}
						<DropdownMenu.Root>
							<DropdownMenu.Trigger>
								<Button variant="ghost" size="icon-xs"
									class="text-gray-400 opacity-0 group-hover:opacity-100 data-[state=open]:opacity-100">
									<Icon name="more-horizontal" size={14} />
								</Button>
							</DropdownMenu.Trigger>
							<DropdownMenu.Content align="end">
								{#if mine}
									<DropdownMenu.Item onclick={() => (editing = true)}>
										<Icon name="pencil" size={13} /> Edit
									</DropdownMenu.Item>
								{/if}
								{#if canDeleteComment(comment, myId, myRole)}
									<DropdownMenu.Item class="text-red-600" onclick={() => void deleteCommentAction(comment.id)}>
										<Icon name="trash" size={13} /> Delete
									</DropdownMenu.Item>
								{/if}
							</DropdownMenu.Content>
						</DropdownMenu.Root>
					{/if}
				</div>
			{/if}
		{/if}
	</div>
</div>

{#if lightboxSrc}
	<ImageLightbox src={lightboxSrc} alt={lightboxAlt} onClose={() => (lightboxSrc = null)} />
{/if}

<style>
	:global(.wos-comment-prose a[href^='#mention-']) {
		color: var(--primary);
		background: color-mix(in srgb, var(--primary) 10%, transparent);
		border-radius: 6px;
		padding: 0 4px;
		font-weight: 600;
		text-decoration: none;
	}
</style>
