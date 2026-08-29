import { describe, expect, it } from 'vitest';
import { chartGeometry, nearestIndex, formatCount } from './analytics';

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
		expect(formatCount(2847)).toBe('2,847');
		expect(formatCount(0)).toBe('0');
		expect(formatCount(999)).toBe('999');
	});
});
