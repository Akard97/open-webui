import { describe, it, expect } from 'vitest';
import { computeScores } from './scoring';
import { THEMES } from './mocks';
import type { Section, ChecklistItem } from './types';

const item = (n: number, result: ChecklistItem['result']): ChecklistItem => ({
	n,
	text: 't',
	code: 'OEC',
	result
});

const one = (theme: string, result: ChecklistItem['result']): Section => ({
	theme,
	id: 'PRP1',
	title: 't',
	codes: 'c',
	intent: 'i',
	items: [item(1, result)]
});

describe('computeScores', () => {
	it('marks Pending review when any human item is open', () => {
		const r = computeScores([one('T1', 'human')], THEMES);
		expect(r.verdict.key).toBe('draft');
		expect(r.humanItemsRemain).toBe(true);
	});

	it('marks Rejected when a gate theme fails', () => {
		const r = computeScores([one('T1', 'non-compliant'), one('T2', 'compliant')], THEMES);
		expect(r.verdict.key).toBe('rejected');
		expect(r.gatesPass).toBe(false);
	});

	it('marks Conditionally Approved when overall is 70-84 and gates pass', () => {
		// T1 = 9/10 (90%, gate passes), T2 = 9/10 (90%, gate passes),
		// T3 = 0/4 (0%) — weighted overall drops into 70..84 band.
		const secs: Section[] = [
			{
				theme: 'T1',
				id: 'PRP1',
				title: 't',
				codes: 'c',
				intent: 'i',
				items: [
					...Array.from({ length: 9 }, (_, i) => item(i + 1, 'compliant')),
					item(10, 'non-compliant')
				]
			},
			{
				theme: 'T2',
				id: 'PRP6',
				title: 't',
				codes: 'c',
				intent: 'i',
				items: [
					...Array.from({ length: 9 }, (_, i) => item(i + 1, 'compliant')),
					item(10, 'non-compliant')
				]
			},
			{
				theme: 'T3',
				id: 'PRP16',
				title: 't',
				codes: 'c',
				intent: 'i',
				items: Array.from({ length: 4 }, (_, i) => item(i + 1, 'non-compliant'))
			}
		];
		const r = computeScores(secs, THEMES);
		expect(r.gatesPass).toBe(true);
		expect(r.verdict.key).toBe('conditional');
	});

	it('marks Approved when overall ≥ 85 and gates pass', () => {
		const secs: Section[] = [
			one('T1', 'compliant'),
			one('T2', 'compliant'),
			one('T3', 'compliant')
		];
		const r = computeScores(secs, THEMES);
		expect(r.overall).toBe(100);
		expect(r.verdict.key).toBe('approved');
	});

	it('uses score = yes / (yes + no), excluding human items from the denominator', () => {
		const secs: Section[] = [
			{
				theme: 'T1',
				id: 'PRP1',
				title: 't',
				codes: 'c',
				intent: 'i',
				items: [
					item(1, 'compliant'),
					item(2, 'non-compliant'),
					item(3, 'human'),
					item(4, 'human')
				]
			}
		];
		const r = computeScores(secs, THEMES);
		const t1 = r.themeRows.find((t) => t.id === 'T1')!;
		expect(t1.pct).toBe(50); // 1 / (1 + 1)
		expect(t1.human).toBe(2);
		expect(r.humanItemsRemain).toBe(true);
	});
});
