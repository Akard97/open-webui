// Pure math for the admin Usage dashboard. The backend buckets heatmap data
// in UTC (row 0 = Sunday); rotation to the viewer's timezone happens here.

export const rotateHeatmap = (utcMatrix: number[][], offsetHours: number): number[][] => {
	// Fractional zones (UTC+5:30 etc.): round to the nearest hour — a fractional
	// index would silently write off-array keys and render the grid empty.
	const offset = Math.round(offsetHours);
	const flat = utcMatrix.flat(); // index = dow * 24 + hour
	const local = new Array(168).fill(0);
	for (let i = 0; i < 168; i++) {
		local[(((i + offset) % 168) + 168) % 168] = flat[i];
	}
	return Array.from({ length: 7 }, (_, d) => local.slice(d * 24, d * 24 + 24));
};

export const busiestHour = (utcHours: number[], offsetHours: number): number | null => {
	if (!utcHours.some((v) => v > 0)) return null;
	const offset = Math.round(offsetHours);
	const local = new Array(24).fill(0);
	for (let h = 0; h < 24; h++) {
		local[(((h + offset) % 24) + 24) % 24] += utcHours[h];
	}
	let best = 0;
	for (let h = 1; h < 24; h++) {
		if (local[h] > local[best]) best = h;
	}
	return best;
};

export const delta = (
	current: number,
	previous: number
): { dir: 'up' | 'down' | 'flat'; pct: number | null } => {
	if (previous === 0) {
		return { dir: current > 0 ? 'up' : 'flat', pct: null };
	}
	if (current === previous) return { dir: 'flat', pct: 0 };
	return {
		dir: current > previous ? 'up' : 'down',
		pct: Math.round(((current - previous) / previous) * 100)
	};
};

export const adoptionPct = (active: number, members: number): string =>
	members > 0 ? `${Math.round((active / members) * 100)}%` : '—';
