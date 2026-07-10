<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog';
	import { Button } from '$lib/components/ui/button';

	export let open = false;
	export let name = '';
	export let busy = false;
	export let onCancel: () => void;
	export let onConfirm: () => void;
</script>

<Dialog.Root {open} onOpenChange={(o) => { if (!o) onCancel(); }}>
	<Dialog.Content class="sm:max-w-md gap-4 rounded-2xl p-6">
		<Dialog.Title class="text-lg">Restrict this workspace?</Dialog.Title>
		<Dialog.Description class="leading-relaxed">
			<span class="font-medium text-gray-700 dark:text-gray-200">{name}</span> will only be visible to its explicit
			members and its creator. Everyone else on the team loses access immediately — it disappears
			from their sidebar and any live sessions are disconnected from its rooms. If you are not a
			member or the creator, that includes you. You can add members afterwards from workspace
			settings.
		</Dialog.Description>
		<div class="flex justify-end gap-2 mt-2">
			<Button variant="outline" size="sm" onclick={onCancel}>Cancel</Button>
			<Button variant="destructive" size="sm" disabled={busy} onclick={onConfirm}>Restrict workspace</Button>
		</div>
	</Dialog.Content>
</Dialog.Root>
