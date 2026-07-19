/** Compact relative age for inbox rows: 45s, 12m, 3h, 2d. */
export function agoShort(ms: number, now = Date.now()): string {
	const s = Math.max(0, Math.floor((now - ms) / 1000));
	if (s < 60) return `${s}s`;
	const m = Math.floor(s / 60);
	if (m < 60) return `${m}m`;
	const h = Math.floor(m / 60);
	if (h < 24) return `${h}h`;
	return `${Math.floor(h / 24)}d`;
}
