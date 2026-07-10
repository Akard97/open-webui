<script lang="ts">
	// Canonical delta badge (spec §4): tinted pill + arrow + tabular value.
	// `up` is the arrow direction; `positive` overrides the color when goodness
	// doesn't track direction (completion time falling is good → down + green).
	import Icon from './Icon.svelte';
	import { tint } from '../lib/colors';

	export let up: boolean;
	export let text: string;
	export let positive: boolean | null = null;

	$: color = (positive ?? up) ? 'var(--wos-done)' : 'var(--wos-danger)';
</script>

<span
	class="inline-flex items-center gap-[3px] rounded-full py-0.5 pr-[7px] pl-[5px] text-[11px] leading-[1.35] font-medium tabular-nums"
	style="color:{color}; background:{tint(color)}"
>
	<Icon name={up ? 'arrow-up' : 'arrow-down'} size={10} strokeWidth={3} />
	<span class="sr-only">{up ? 'up' : 'down'} </span>{text}
</span>
