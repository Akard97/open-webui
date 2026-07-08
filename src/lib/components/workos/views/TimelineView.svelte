<script lang="ts">
	import FilterBar from '../chrome/FilterBar.svelte';
	import { boardFilter } from '../lib/store';
</script>

<div class="h-full flex flex-col min-h-0">
	<FilterBar filter={boardFilter} />
	<div class="flex-1 flex items-center justify-center text-sm text-gray-400">Timeline</div>
</div>
