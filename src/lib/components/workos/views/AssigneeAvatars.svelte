<script lang="ts">
	import { Avatar, AvatarFallback, AvatarGroup, AvatarGroupCount, AvatarImage } from '$lib/components/ui/avatar';
	import { avatarColors } from '../lib/avatar';
	import { initials, displayName, directory } from '../lib/store';

	export let ids: string[] = [];
	export let max = 4;
	export let size = 24; // px

	// Only 20/24/32 are legal avatar sizes — clamp anything else to the nearest one,
	// preferring the larger size on an exact tie (e.g. legacy 22px -> 24px).
	const LEGAL_SIZES = [20, 24, 32];
	function clampSize(px: number): number {
		return LEGAL_SIZES.reduce((best, s) => {
			const d = Math.abs(s - px);
			const bd = Math.abs(best - px);
			return d < bd || (d === bd && s > best) ? s : best;
		});
	}

	$: shown = (ids ?? []).slice(0, max);
	$: overflow = Math.max(0, (ids ?? []).length - shown.length);
	$: px = clampSize(size);
	$: fontSize = Math.round(px * 0.42);
</script>

{#if (ids ?? []).length}
	<AvatarGroup class="-space-x-[7px]">
		{#each shown as id (id)}
			{@const colors = avatarColors(id)}
			{@const image = $directory[id]?.image ?? null}
			<Avatar style="width:{px}px;height:{px}px" title={displayName(id)}>
				{#if image}<AvatarImage src={image} alt="" />{/if}
				<AvatarFallback
					class="font-semibold"
					style="background:{colors.background};color:{colors.foreground};font-size:{fontSize}px"
				>{initials(id)}</AvatarFallback>
			</Avatar>
		{/each}
		{#if overflow}
			<AvatarGroupCount
				class="bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 font-semibold"
				style="width:{px}px;height:{px}px;font-size:{fontSize}px"
				title={(ids ?? []).slice(max).map((id) => displayName(id)).join(', ')}
			>+{overflow}</AvatarGroupCount>
		{/if}
	</AvatarGroup>
{/if}
