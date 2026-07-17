import { describe, expect, it } from 'vitest';

import {
	EFFORT_LEVELS,
	functionIdFromModelId,
	indexToLevel,
	levelIndex,
	mergeEffort,
	normalizeEffort,
	specHasEffort
} from './effort';

describe('EFFORT_LEVELS', () => {
	it('is exactly default/xhigh/max in order', () => {
		expect([...EFFORT_LEVELS]).toEqual(['default', 'xhigh', 'max']);
	});
});

describe('normalizeEffort', () => {
	it('passes through valid levels', () => {
		expect(normalizeEffort('default')).toBe('default');
		expect(normalizeEffort('xhigh')).toBe('xhigh');
		expect(normalizeEffort('max')).toBe('max');
	});

	it('falls back to default for unknown/missing values', () => {
		expect(normalizeEffort('turbo')).toBe('default');
		expect(normalizeEffort('')).toBe('default');
		expect(normalizeEffort(undefined)).toBe('default');
		expect(normalizeEffort(null)).toBe('default');
		expect(normalizeEffort(3)).toBe('default');
		expect(normalizeEffort({})).toBe('default');
	});
});

describe('levelIndex / indexToLevel', () => {
	it('round-trips all levels', () => {
		for (const level of EFFORT_LEVELS) {
			expect(indexToLevel(levelIndex(level))).toBe(level);
		}
	});

	it('clamps out-of-range indices', () => {
		expect(indexToLevel(-1)).toBe('default');
		expect(indexToLevel(5)).toBe('max');
	});

	it('rounds fractional indices to nearest stop', () => {
		expect(indexToLevel(0.4)).toBe('default');
		expect(indexToLevel(0.6)).toBe('xhigh');
		expect(indexToLevel(1.5)).toBe('max');
	});
});

describe('functionIdFromModelId', () => {
	it('takes the prefix before the first dot', () => {
		expect(functionIdFromModelId('osool_pipe.osool-ai')).toBe('osool_pipe');
	});

	it('returns dotless ids unchanged', () => {
		expect(functionIdFromModelId('osool_pipe')).toBe('osool_pipe');
	});
});

describe('specHasEffort', () => {
	it('accepts a pydantic UserValves spec exposing all three levels', () => {
		const spec = {
			properties: {
				EFFORT: {
					default: 'default',
					description: 'Reasoning effort',
					enum: ['default', 'xhigh', 'max'],
					title: 'Effort',
					type: 'string'
				}
			},
			title: 'UserValves',
			type: 'object'
		};
		expect(specHasEffort(spec)).toBe(true);
	});

	it('accepts extra enum values as long as the three levels are present', () => {
		expect(
			specHasEffort({
				properties: { EFFORT: { enum: ['default', 'xhigh', 'max', 'low'] } }
			})
		).toBe(true);
	});

	it('rejects specs without EFFORT, with partial enums, or garbage input', () => {
		expect(specHasEffort({ properties: {} })).toBe(false);
		expect(specHasEffort({ properties: { EFFORT: { enum: ['default', 'max'] } } })).toBe(false);
		expect(specHasEffort({ properties: { EFFORT: { type: 'string' } } })).toBe(false);
		expect(specHasEffort(null)).toBe(false);
		expect(specHasEffort(undefined)).toBe(false);
		expect(specHasEffort('spec')).toBe(false);
	});
});

describe('mergeEffort', () => {
	it('preserves unrelated valve keys', () => {
		expect(mergeEffort({ EFFORT: 'default', OTHER: 42 }, 'max')).toEqual({
			EFFORT: 'max',
			OTHER: 42
		});
	});

	it('builds a fresh object from null/undefined/array/non-object valves', () => {
		expect(mergeEffort(null, 'xhigh')).toEqual({ EFFORT: 'xhigh' });
		expect(mergeEffort(undefined, 'xhigh')).toEqual({ EFFORT: 'xhigh' });
		expect(mergeEffort([1, 2], 'xhigh')).toEqual({ EFFORT: 'xhigh' });
		expect(mergeEffort('nope', 'xhigh')).toEqual({ EFFORT: 'xhigh' });
	});

	it('does not mutate the input valves object', () => {
		const valves = { EFFORT: 'default' };
		mergeEffort(valves, 'max');
		expect(valves.EFFORT).toBe('default');
	});
});
