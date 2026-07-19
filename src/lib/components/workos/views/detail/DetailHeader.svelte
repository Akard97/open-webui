<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { Button, buttonVariants } from '$lib/components/ui/button';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { cn } from '$lib/components/ui/utils.js';
	import { STATUS_LABEL, type Task } from '../../lib/types';
	import { currentWorkstream, closeTask, removeTask, roles, workstreams } from '../../lib/store';
	import { user } from '$lib/stores';
	import { canDeleteTask } from '../../lib/roles';

	export let task: Task;
	export let onEditTitle: () => void;

	$: myRole = $roles[task.team_id];
	$: crumb =
		$workstreams.find((w) => w.id === task.workstream_id)?.name ?? $currentWorkstream?.name ?? 'Tasks';

	let copied = false;
	async function copyLink() {
		try {
			await navigator.clipboard.writeText(window.location.href);
			copied = true;
			setTimeout(() => (copied = false), 1500);
		} catch {
			/* clipboard unavailable */
		}
	}
</script>

<div class="flex items-center gap-1 px-2.5 h-12 shrink-0 border-b border-gray-200 dark:border-gray-800">
	<Button variant="ghost" size="icon-sm" title="Back" class="md:hidden text-gray-500" onclick={closeTask}>
		<Icon name="arrow-left" size={18} />
	</Button>
	<Button variant="ghost" size="icon-sm" title="Expand" class="hidden md:inline-flex text-gray-400">
		<Icon name="maximize" size={16} />
	</Button>
	<div class="flex items-center gap-1.5 min-w-0 text-xs text-gray-400">
		<span class="truncate">{crumb}</span>
		<Icon name="chevron-right" size={12} />
		<span class="truncate text-gray-500 dark:text-gray-300">{STATUS_LABEL[task.status]}</span>
	</div>
	<div class="flex-1"></div>
	<Button variant="ghost" size="icon-sm" title="Edit title" class="text-gray-500" onclick={onEditTitle}>
		<Icon name="pencil" size={15} />
	</Button>
	<Button variant="ghost" size="icon-sm" title={copied ? 'Copied!' : 'Copy link'} class="text-gray-500" onclick={copyLink}>
		<Icon name={copied ? 'check' : 'share-2'} size={15} />
	</Button>
	<DropdownMenu.Root>
		<DropdownMenu.Trigger title="More" class={cn(buttonVariants({ variant: 'ghost', size: 'icon-sm' }), 'text-gray-500')}>
			<Icon name="more-horizontal" size={16} />
		</DropdownMenu.Trigger>
		<DropdownMenu.Content align="end">
			{#if canDeleteTask(task, $user?.id ?? '', myRole)}
				<DropdownMenu.Item class="text-red-600" onSelect={() => removeTask(task.id)}>
					<span class="inline-flex items-center gap-2"><Icon name="trash" size={14} /> Delete task</span>
				</DropdownMenu.Item>
			{:else}
				<DropdownMenu.Item disabled>No actions available</DropdownMenu.Item>
			{/if}
		</DropdownMenu.Content>
	</DropdownMenu.Root>
	<Button variant="ghost" size="icon-sm" title="Close" class="max-md:hidden text-gray-500" onclick={closeTask}>
		<Icon name="x" size={16} />
	</Button>
</div>
