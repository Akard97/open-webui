<script lang="ts">
	import Icon from '../../ui/Icon.svelte';

	export let icon: string;
	export let label: string;
	export let align: 'center' | 'start' = 'center';
</script>

<div class="flex gap-3 min-h-9 {align === 'start' ? 'items-start' : 'items-center'}">
	<span
		class="flex items-center gap-2 w-28 flex-none text-[13px] text-gray-600 dark:text-gray-300 {align === 'start' ? 'pt-1.5' : ''}"
	>
		<Icon name={icon} size={15} />
		{label}
	</span>
	<div class="flex-1 min-w-0 text-sm">
		<slot />
	</div>
</div>
