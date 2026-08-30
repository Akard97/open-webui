export type SeriesPoint = { day: string; views: number };

export type ChartGeometry = {
	points: [number, number][];
	line: string;
	area: string;
	gridlines: { value: number; y: number }[];
	labeled: number[];
};

// Top padding leaves room for the data labels drawn above peak points.
const PAD_TOP = 16;
const PAD_BOTTOM = 4;
const MAX_LABELS = 8;

// Indices worth a persistent data label: local peaks at or above half the
// series maximum. Hover covers every other point, so minor bumps stay
// unlabeled rather than turning a busy series into a wall of numbers. A
// plateau labels only its first day.
const labeledIndices = (views: number[], rawMax: number): number[] => {
	if (rawMax <= 0) return [];
	const peaks = views
		.map((v, i) => ({ v, i }))
		.filter(({ v, i }) => {
			const prev = i > 0 ? views[i - 1] : -Infinity;
			const next = i < views.length - 1 ? views[i + 1] : -Infinity;
			return v > 0 && v >= rawMax / 2 && v > prev && v >= next;
		});
	return peaks
		.sort((a, b) => b.v - a.v)
		.slice(0, MAX_LABELS)
		.map(({ i }) => i)
		.sort((a, b) => a - b);
};

export const chartGeometry = (
	series: SeriesPoint[],
	width: number,
	height: number
): ChartGeometry => {
	if (series.length === 0) return { points: [], line: '', area: '', gridlines: [], labeled: [] };

	// An all-zero series would divide by zero; a single point would divide by
	// zero on the x axis. Both are normal states (a brand-new site, a 1-day
	// window), so they're guarded to render as a flat line (all-zero) or a
	// single point at the top of the canvas (one point, since `max` becomes
	// that point's own value) rather than as NaN.
	const views = series.map((p) => p.views);
	const rawMax = Math.max(...views);
	const max = Math.max(rawMax, 1);
	const span = height - PAD_TOP - PAD_BOTTOM;
	const step = series.length > 1 ? width / (series.length - 1) : 0;

	const points = series.map(
		(p, i) => [i * step, height - PAD_BOTTOM - (p.views / max) * span] as [number, number]
	);

	const line = points
		.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`)
		.join(' ');
	const area = `${line} L${points[points.length - 1][0].toFixed(1)},${height} L${points[0][0].toFixed(1)},${height} Z`;

	// Reference lines at the max and (when there is room) the halfway value.
	// Only real data earns a gridline: the all-zero fallback max of 1 would
	// otherwise draw a line for a value that never happened.
	const yFor = (v: number) => height - PAD_BOTTOM - (v / max) * span;
	const gridlines: { value: number; y: number }[] = [];
	if (rawMax >= 1) gridlines.push({ value: rawMax, y: yFor(rawMax) });
	if (rawMax >= 2) {
		const mid = Math.round(rawMax / 2);
		if (mid > 0 && mid < rawMax) gridlines.push({ value: mid, y: yFor(mid) });
	}

	return { points, line, area, gridlines, labeled: labeledIndices(views, rawMax) };
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

export const viewerInitials = (name: string): string => {
	// Array.from, not slice: a name may start with a character outside the
	// BMP, and cutting a surrogate pair in half renders a replacement box.
	const words = name.trim().split(/\s+/).filter(Boolean);
	if (words.length === 0) return '?';
	return words
		.slice(0, 2)
		.map((w) => Array.from(w)[0] ?? '')
		.join('')
		.toUpperCase();
};
