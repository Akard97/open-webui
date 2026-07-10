<script lang="ts">
	import SidebarIcon from '$lib/components/icons/Sidebar.svelte';
	import { Button } from '$lib/components/ui/button';
	import { view, currentWorkstream, workspaces, unreadCount, mobileNavOpen } from '../lib/store';

	// Global views carry a fixed label; workstream views show the breadcrumb title.
	const LABELS: Record<string, string> = { mywork: 'My Work', inbox: 'Inbox', admin: 'Admin' };
	$: ws = $currentWorkstream;
	$: parentWorkspace = ws ? $workspaces.find((w) => w.id === ws.workspace_id) : null;
	$: title =
		LABELS[$view] ?? (ws ? `${parentWorkspace ? `${parentWorkspace.name} · ` : ''}${ws.name}` : 'WorkOS');
</script>

<!-- Mobile WorkOS header: sits under the global app bar, mirrors the chat tool's
     own header row — the toggle opens the WorkOS nav drawer. -->
<div
	class="flex-none h-11 flex items-center gap-1 px-2 border-b border-gray-100 dark:border-gray-850 bg-white dark:bg-gray-950"
>
	<Button
		variant="ghost"
		size="icon-lg"
		class="relative"
		title="Open WorkOS navigation"
		aria-label="Open WorkOS navigation"
		onclick={() => mobileNavOpen.set(true)}
	>
		<SidebarIcon className="size-5" />
		{#if $unreadCount > 0}
			<span class="absolute top-1 right-1 size-1.5 rounded-full bg-sky-500"></span>
		{/if}
	</Button>
	<div class="flex-1 min-w-0 text-sm font-medium truncate px-1">{title}</div>
</div>
