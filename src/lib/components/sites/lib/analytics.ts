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
	// window), so they're guarded to render as a flat line (all-zero) or a
	// single point at the top of the canvas (one point, since `max` becomes
	// that point's own value) rather than as NaN.
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
	// A zero-width canvas (e.g. measured while hidden) makes x / width either
	// NaN (x === 0) or Infinity (x !== 0); guard it directly rather than
	// relying on Math.min/Math.max, which don't clamp NaN.
	if (width <= 0) return 0;
	const ratio = Math.min(1, Math.max(0, x / width));
	return Math.round(ratio * (series.length - 1));
};

export const formatCount = (n: number, locale: string): string => {
	// The locale is passed in, never read from i18n here: this module is pure
	// and unit-tested. A malformed BCP-47 tag makes the Intl constructor
	// throw, and a number in a card is not worth taking the pane down for, so
	// fall back to the runtime default rather than propagating a RangeError.
	try {
		return new Intl.NumberFormat(locale).format(n);
	} catch {
		return new Intl.NumberFormat().format(n);
	}
};
