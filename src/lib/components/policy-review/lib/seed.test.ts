import { describe, it, expect } from 'vitest';
import { buildActiveVersion, buildSeedReviews, ACTIVE_VERSION_ID } from './seed';

describe('buildActiveVersion', () => {
	it('produces a definition with 6 themes and 70 items, no answers', () => {
		const v = buildActiveVersion();
		expect(v.id).toBe(ACTIVE_VERSION_ID);
		expect(v.themes).toHaveLength(6);
		const items = v.sections.flatMap((s) => s.items);
		expect(items).toHaveLength(70);
		expect((items[0] as Record<string, unknown>).result).toBeUndefined();
	});

	it('flags [H] items as human assessment and strips the suffix', () => {
		const v = buildActiveVersion();
		const human = v.sections.flatMap((s) => s.items).filter((i) => i.assessment === 'human');
		expect(human.length).toBeGreaterThan(0);
		expect(human.every((i) => !i.text.includes('[H]'))).toBe(true);
	});

	it('gives every item a stable id of form PRP<x>-<n>', () => {
		const v = buildActiveVersion();
		const ids = v.sections.flatMap((s) => s.items.map((i) => i.id));
		expect(new Set(ids).size).toBe(ids.length);
		expect(ids.every((id) => /^PRP\d+-\d+$/.test(id))).toBe(true);
	});
});

describe('buildSeedReviews', () => {
	it('seeds one draft, two pending, one approved, one rejected', () => {
		const r = buildSeedReviews();
		const by = (s: string) => r.filter((x) => x.status === s).length;
		expect(by('draft')).toBe(1);
		expect(by('pending')).toBe(2);
		expect(by('approved')).toBe(1);
		expect(by('rejected')).toBe(1);
	});

	it('pending/approved reviews have no unresolved human items', () => {
		const r = buildSeedReviews().filter((x) => x.status === 'pending' || x.status === 'approved');
		r.forEach((rev) => {
			const human = Object.values(rev.results).filter((v) => v.result === 'human');
			expect(human).toHaveLength(0);
		});
	});
});
