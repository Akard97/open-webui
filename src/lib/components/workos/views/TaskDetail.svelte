<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog';
	import TaskDetailBody from './detail/TaskDetailBody.svelte';
	import { selectedTask, closeTask } from '../lib/store';

	$: t = $selectedTask;
</script>

{#if t}
	<Dialog.Root open={true} onOpenChange={(o) => { if (!o) closeTask(); }}>
		<Dialog.Content
			showCloseButton={false}
			class="flex flex-col gap-0 p-0 overflow-hidden w-[95vw] max-w-[1100px] sm:max-w-[1100px] max-h-[85vh] max-md:w-screen max-md:max-w-none max-md:h-dvh max-md:max-h-dvh max-md:rounded-none max-md:border-0 bg-white dark:bg-gray-950"
		>
			<Dialog.Title class="sr-only">{t.title}</Dialog.Title>
			<Dialog.Description class="sr-only">Task details</Dialog.Description>
			<TaskDetailBody />
		</Dialog.Content>
	</Dialog.Root>
{/if}
