export type SeriesPoint = { day: string; views: number };

export type ChartGeometry = {
	points: [number, number][];
	line: string;
	area: string;
};

const PAD_TOP = 8;
const PAD_BOTTOM = 4;

export const chartGeometry = (
	series: SeriesPoint[],
	width: number,
	height: number
): ChartGeometry => {
	if (series.length === 0) return { points: [], line: '', area: '' };

	// An all-zero series would divide by zero; a single point would divide by
	// zero on the x axis. Both are normal states (a brand-new site, a 1-day
	// window), so they render flat along the baseline rather than as NaN.
	const max = Math.max(...series.map((p) => p.views), 1);
	const span = height - PAD_TOP - PAD_BOTTOM;
	const step = series.length > 1 ? width / (series.length - 1) : 0;

	const points = series.map(
		(p, i) => [i * step, height - PAD_BOTTOM - (p.views / max) * span] as [number, number]
	);

	const line = points
		.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`)
		.join(' ');
	const area = `${line} L${points[points.length - 1][0].toFixed(1)},${height} L${points[0][0].toFixed(1)},${height} Z`;

	return { points, line, area };
};

export const nearestIndex = (series: SeriesPoint[], x: number, width: number): number => {
	if (series.length === 0) return 0;
	const ratio = Math.min(1, Math.max(0, x / width));
	return Math.round(ratio * (series.length - 1));
};

export const formatCount = (n: number): string => new Intl.NumberFormat('en-US').format(n);
