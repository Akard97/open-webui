<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { attachments, removeAttachment, roles, currentTeam } from '../../lib/store';
	import { user } from '$lib/stores';
	import { canDeleteAttachment } from '../../lib/roles';
	import * as api from '../../lib/api';

	$: myRole = $currentTeam ? $roles[$currentTeam.id] : undefined;
	$: taskFiles = $attachments.filter((a) => !a.comment_id);
	const isImage = (ct?: string | null) => !!ct && ct.startsWith('image/');
</script>

{#if taskFiles.length}
	<div class="pt-4">
		<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-2">Files</div>
		<div class="space-y-1.5">
			{#each taskFiles as a (a.id)}
				<div class="flex items-center gap-2 group">
					{#if isImage(a.content_type)}
						<img src={api.attachmentUrl(a.id)} alt={a.name} class="w-8 h-8 rounded object-cover flex-none" />
					{:else}
						<Icon name="paperclip" size={16} />
					{/if}
					<a class="text-sm text-teal-600 truncate flex-1" href={api.attachmentUrl(a.id)} target="_blank" rel="noreferrer">{a.name}</a>
					<span class="text-[11px] text-gray-400">{Math.max(1, Math.round(a.size / 1024))} KB</span>
					{#if canDeleteAttachment(a, $user?.id ?? '', myRole)}
						<button class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500" title="Remove" onclick={() => removeAttachment(a.id)}><Icon name="trash" size={13} /></button>
					{/if}
				</div>
			{/each}
		</div>
	</div>
{/if}
