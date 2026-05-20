<script lang="ts">
	import type { Verdict } from '../lib/types';

	let { verdict }: { verdict: Verdict } = $props();
</script>

<span class="verdict-badge {verdict.key}">
	<span class="pulse"></span>
	{verdict.label}
</span>
