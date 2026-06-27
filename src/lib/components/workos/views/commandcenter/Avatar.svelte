<script lang="ts">
	export let name = '';
	export let size = 22;

	// Osool accent ramp (teal-led), deterministic by name hash.
	const PALETTE = ['#00a5ba', '#769a4a', '#d97706', '#dc2626', '#7c3aed', '#0ea5e9', '#db2777', '#ca8a04'];
	function hash(s: string): number {
		let h = 0;
		for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
		return Math.abs(h);
	}
	$: clean = (name || '?').trim();
	$: initials = clean.split(/\s+/).map((w) => w[0]).slice(0, 2).join('').toUpperCase() || '?';
	$: color = PALETTE[hash(clean) % PALETTE.length];
</script>

<span
	class="rounded-full inline-flex items-center justify-center font-medium text-white flex-none"
	style="width:{size}px;height:{size}px;background:{color};font-size:{Math.round(size * 0.42)}px"
	title={clean}
>{initials}</span>
