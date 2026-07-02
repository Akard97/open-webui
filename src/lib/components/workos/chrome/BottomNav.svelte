<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import { view, unreadCount, mobileNavOpen } from '../lib/store';

	// Workstream-scoped views (and admin, reached via the drawer) light up Browse.
	$: browseActive = ['board', 'list', 'calendar', 'overview', 'admin'].includes($view);
</script>

<nav class="flex-none flex border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 pb-[env(safe-area-inset-bottom)]">
	<button
		class="flex-1 flex flex-col items-center gap-0.5 py-2 text-[10px] font-medium {$view === 'mywork' ? 'text-primary' : 'text-gray-500 dark:text-gray-400'}"
		onclick={() => view.set('mywork')}
	>
		<Icon name="check" size={20} /> My Work
	</button>
	<button
		class="relative flex-1 flex flex-col items-center gap-0.5 py-2 text-[10px] font-medium {$view === 'inbox' ? 'text-primary' : 'text-gray-500 dark:text-gray-400'}"
		onclick={() => view.set('inbox')}
	>
		<Icon name="message-square" size={20} /> Inbox
		{#if $unreadCount > 0}
			<span class="absolute top-1.5 right-[32%] size-1.5 rounded-full bg-sky-500"></span>
		{/if}
	</button>
	<button
		class="flex-1 flex flex-col items-center gap-0.5 py-2 text-[10px] font-medium {browseActive ? 'text-primary' : 'text-gray-500 dark:text-gray-400'}"
		onclick={() => mobileNavOpen.set(true)}
	>
		<Icon name="layers" size={20} /> Browse
	</button>
</nav>
