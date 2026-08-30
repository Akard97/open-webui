import { describe, expect, it } from 'vitest';
import { chartGeometry, nearestIndex, formatCount, viewerInitials } from './analytics';

const pts = (...views: number[]) =>
	views.map((v, i) => ({ day: `2026-08-${String(i + 1).padStart(2, '0')}`, views: v }));

describe('chartGeometry', () => {
	it('spans the full width and starts the path with a moveto', () => {
		const g = chartGeometry(pts(0, 5, 10), 100, 50);
		expect(g.points[0][0]).toBe(0);
		expect(g.points[2][0]).toBe(100);
		expect(g.line.startsWith('M')).toBe(true);
	});

	it('puts the largest value highest on the canvas', () => {
		const g = chartGeometry(pts(1, 9), 100, 50);
		expect(g.points[1][1]).toBeLessThan(g.points[0][1]);
	});

	it('produces no NaN for an all-zero series', () => {
		const g = chartGeometry(pts(0, 0, 0), 100, 50);
		expect(g.line).not.toContain('NaN');
		expect(g.area).not.toContain('NaN');
	});

	it('produces no NaN for a single point', () => {
		const g = chartGeometry(pts(7), 100, 50);
		expect(g.line).not.toContain('NaN');
		expect(g.area).not.toContain('NaN');
		expect(g.points).toHaveLength(1);
	});

	it('returns empty geometry for an empty series', () => {
		const g = chartGeometry([], 100, 50);
		expect(g.points).toEqual([]);
		expect(g.line).toBe('');
		expect(g.area).toBe('');
		expect(g.gridlines).toEqual([]);
		expect(g.labeled).toEqual([]);
	});

	it('draws gridlines at the max and midpoint of real data', () => {
		const g = chartGeometry(pts(0, 2, 4), 100, 50);
		expect(g.gridlines.map((l) => l.value)).toEqual([4, 2]);
		// The max line sits exactly on the highest point's y.
		expect(g.gridlines[0].y).toBeCloseTo(g.points[2][1]);
		expect(g.gridlines[0].y).toBeLessThan(g.gridlines[1].y);
	});

	it('skips the midpoint gridline when the max is 1', () => {
		const g = chartGeometry(pts(0, 1), 100, 50);
		expect(g.gridlines.map((l) => l.value)).toEqual([1]);
	});

	it('draws no gridlines for an all-zero series', () => {
		const g = chartGeometry(pts(0, 0, 0), 100, 50);
		expect(g.gridlines).toEqual([]);
	});

	it('labels local peaks at or above half the max', () => {
		// Peaks at 4 (index 2) and 3 (index 5); the bump of 1 stays unlabeled.
		const g = chartGeometry(pts(0, 2, 4, 0, 1, 3, 0), 100, 50);
		expect(g.labeled).toEqual([2, 5]);
	});

	it('labels only the first day of a plateau', () => {
		const g = chartGeometry(pts(0, 3, 3, 0), 100, 50);
		expect(g.labeled).toEqual([1]);
	});

	it('labels a rising endpoint', () => {
		const g = chartGeometry(pts(0, 0, 2, 4), 100, 50);
		expect(g.labeled).toContain(3);
	});

	it('labels nothing for an all-zero series', () => {
		const g = chartGeometry(pts(0, 0, 0), 100, 50);
		expect(g.labeled).toEqual([]);
	});

	it('caps data labels at eight, keeping the largest values', () => {
		// Ten isolated peaks of increasing height, all above half the max.
		const views: number[] = [];
		for (let i = 1; i <= 10; i++) views.push(20 + i, 0);
		const g = chartGeometry(pts(...views), 100, 50);
		expect(g.labeled).toHaveLength(8);
		// The two smallest peaks (values 21 and 22, at indices 0 and 2) drop.
		expect(g.labeled).not.toContain(0);
		expect(g.labeled).not.toContain(2);
	});

	it('closes the area path back to the baseline', () => {
		const g = chartGeometry(pts(1, 2), 100, 50);
		expect(g.area.endsWith('Z')).toBe(true);
	});
});

describe('nearestIndex', () => {
	it('maps an x offset to the closest point', () => {
		const s = pts(1, 2, 3, 4, 5);
		expect(nearestIndex(s, 0, 100)).toBe(0);
		expect(nearestIndex(s, 100, 100)).toBe(4);
		expect(nearestIndex(s, 51, 100)).toBe(2);
	});

	it('clamps outside the canvas instead of returning a bad index', () => {
		const s = pts(1, 2, 3);
		expect(nearestIndex(s, -20, 100)).toBe(0);
		expect(nearestIndex(s, 999, 100)).toBe(2);
	});

	it('returns 0 for an empty series', () => {
		expect(nearestIndex([], 10, 100)).toBe(0);
	});

	it('clamps to index 0 when the canvas has zero width and x is zero', () => {
		const s = pts(1, 2, 3);
		const idx = nearestIndex(s, 0, 0);
		expect(idx).toBe(0);
		expect(Number.isInteger(idx)).toBe(true);
	});

	it('clamps to a valid index when the canvas has zero width and x is non-zero', () => {
		const s = pts(1, 2, 3);
		const idx = nearestIndex(s, 40, 0);
		expect(idx).toBe(0);
		expect(Number.isInteger(idx)).toBe(true);
	});
});

describe('formatCount', () => {
	it('adds thousands separators', () => {
		expect(formatCount(2847, 'en-US')).toBe('2,847');
		expect(formatCount(0, 'en-US')).toBe('0');
		expect(formatCount(999, 'en-US')).toBe('999');
	});

	it('groups by the locale it is given, not a hardcoded one', () => {
		expect(formatCount(2847, 'de-DE')).toBe('2.847');
	});

	it('falls back to the runtime default for a malformed tag', () => {
		expect(formatCount(2847, 'en_US')).toBe(new Intl.NumberFormat().format(2847));
	});
});

describe('viewerInitials', () => {
	it('takes the first letter of the first two words', () => {
		expect(viewerInitials('Sara Al-Mutairi')).toBe('SA');
		expect(viewerInitials('Omar')).toBe('O');
	});

	it('ignores extra whitespace', () => {
		expect(viewerInitials('  Sara   Al-Mutairi  ')).toBe('SA');
	});

	it('returns a placeholder rather than nothing for an empty name', () => {
		expect(viewerInitials('')).toBe('?');
		expect(viewerInitials('   ')).toBe('?');
	});

	it('handles non-Latin names without mangling them', () => {
		expect(viewerInitials('سارة المطيري')).toBe('سا');
	});
});
