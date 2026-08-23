import { describe, expect, it } from 'vitest';
import { adoptionPct, busiestHour, delta, rotateHeatmap } from './usageStats';

const empty = () => Array.from({ length: 7 }, () => new Array(24).fill(0));

describe('rotateHeatmap', () => {
	it('is identity at offset 0', () => {
		const m = empty();
		m[1][10] = 5;
		expect(rotateHeatmap(m, 0)[1][10]).toBe(5);
	});

	it('shifts forward for positive offsets (UTC+3)', () => {
		const m = empty();
		m[1][10] = 5; // Monday 10:00 UTC
		const local = rotateHeatmap(m, 3);
		expect(local[1][13]).toBe(5); // Monday 13:00 local
		expect(local[1][10]).toBe(0);
	});

	it('wraps across day boundaries', () => {
		const m = empty();
		m[6][23] = 7; // Saturday 23:00 UTC
		const local = rotateHeatmap(m, 3);
		expect(local[0][2]).toBe(7); // Sunday 02:00 local (wraps week)
	});

	it('handles negative offsets', () => {
		const m = empty();
		m[0][0] = 4; // Sunday 00:00 UTC
		const local = rotateHeatmap(m, -5);
		expect(local[6][19]).toBe(4); // Saturday 19:00 local
	});

	it('rounds fractional offsets to the nearest hour (UTC+5:30)', () => {
		const m = empty();
		m[1][10] = 5;
		expect(rotateHeatmap(m, 5.5)[1][16]).toBe(5); // rounds to +6
	});
});

describe('busiestHour', () => {
	it('returns the rotated max hour', () => {
		const hours = new Array(24).fill(0);
		hours[10] = 9;
		expect(busiestHour(hours, 3)).toBe(13);
	});

	it('returns null when empty', () => {
		expect(busiestHour(new Array(24).fill(0), 3)).toBeNull();
	});

	it('rounds fractional offsets', () => {
		const hours = new Array(24).fill(0);
		hours[10] = 9;
		expect(busiestHour(hours, 5.5)).toBe(16);
	});
});

describe('delta', () => {
	it('computes direction and pct', () => {
		expect(delta(150, 100)).toEqual({ dir: 'up', pct: 50 });
		expect(delta(50, 100)).toEqual({ dir: 'down', pct: -50 });
		expect(delta(100, 100)).toEqual({ dir: 'flat', pct: 0 });
	});

	it('handles zero previous', () => {
		expect(delta(5, 0)).toEqual({ dir: 'up', pct: null });
		expect(delta(0, 0)).toEqual({ dir: 'flat', pct: null });
	});
});

describe('adoptionPct', () => {
	it('formats percentage', () => {
		expect(adoptionPct(5, 8)).toBe('63%');
	});
	it('em-dash for empty groups', () => {
		expect(adoptionPct(0, 0)).toBe('—');
	});
});
