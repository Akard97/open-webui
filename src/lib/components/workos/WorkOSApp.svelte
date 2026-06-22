<script lang="ts">
	import Clipboard from '$lib/components/icons/Clipboard.svelte';

	// Placeholder shell for the WorkOS task-management tool. Intentionally minimal
	// — this is the file the real tool will grow out of.
</script>

<div class="w-full h-full flex items-center justify-center p-6 text-gray-700 dark:text-gray-200">
	<div class="flex flex-col items-center text-center max-w-md">
		<div
			class="flex items-center justify-center size-16 rounded-2xl bg-gray-100 dark:bg-gray-850 text-gray-500 dark:text-gray-300 mb-5"
		>
			<Clipboard className="size-8" strokeWidth="1.5" />
		</div>

		<h1 class="text-2xl font-semibold mb-2">WorkOS</h1>

		<p class="text-sm text-gray-500 dark:text-gray-400">
			Task management is coming soon. This space is reserved while we build it out.
		</p>
	</div>
</div>
