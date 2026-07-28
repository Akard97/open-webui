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

/** Long-form relative time for comment headers: "just now", "58 minutes ago",
 * "2 hours ago", "3 days ago"; older than a week falls back to a short date. */
export function agoLong(ts: number, now: number = Date.now()): string {
	const s = Math.max(0, Math.floor((now - ts) / 1000));
	if (s < 60) return 'just now';
	const m = Math.floor(s / 60);
	if (m < 60) return `${m} minute${m === 1 ? '' : 's'} ago`;
	const h = Math.floor(m / 60);
	if (h < 24) return `${h} hour${h === 1 ? '' : 's'} ago`;
	const d = Math.floor(h / 24);
	if (d < 7) return `${d} day${d === 1 ? '' : 's'} ago`;
	return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
