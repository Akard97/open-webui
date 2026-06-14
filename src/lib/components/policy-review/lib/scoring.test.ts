import { describe, it, expect } from 'vitest';
import { computeScores } from './scoring';
import type { ChecklistVersion, ItemResult, Theme } from './types';

const THEMES: Theme[] = [
	{ id: 'T1', name: 'Policy Foundation', weight: 28, gate: true, threshold: 85 },
	{ id: 'T2', name: 'Governance and Accountability', weight: 28, gate: true, threshold: 85 },
	{ id: 'T3', name: 'People and Communication', weight: 16, gate: false },
	{ id: 'T4', name: 'Performance and Measurement', weight: 14, gate: false },
	{ id: 'T5', name: 'Implementation and Change', weight: 7, gate: false },
	{ id: 'T6', name: 'Policy Integrity', weight: 7, gate: false }
];

const VERDICT_BANDS = { approved: 85, conditional: 70 };

function version(themeIds: string[]): ChecklistVersion {
	return {
		id: 'v',
		label: 'v',
		status: 'active',
		publishedAt: null,
		publishedBy: null,
		changeSummary: '',
		themes: THEMES,
		verdictBands: VERDICT_BANDS,
		sections: themeIds.map((t, i) => ({
			id: `PRP${i + 1}`,
			theme: t,
			title: 't',
			codes: 'c',
			intent: 'i',
			items: [{ id: `PRP${i + 1}-1`, n: 1, text: 't', codes: 'OEC', assessment: 'auto' as const }]
		}))
	};
}

const res = (pairs: Record<string, ItemResult['result']>): Record<string, ItemResult> =>
	Object.fromEntries(Object.entries(pairs).map(([k, v]) => [k, { result: v }]));

describe('computeScores', () => {
	it('marks Pending review when any human item is open', () => {
		const r = computeScores(version(['T1']), res({ 'PRP1-1': 'human' }));
		expect(r.verdict.key).toBe('draft');
		expect(r.humanItemsRemain).toBe(true);
	});

	it('marks Rejected when a gate theme fails', () => {
		const r = computeScores(version(['T1', 'T2']), res({ 'PRP1-1': 'non-compliant', 'PRP2-1': 'compliant' }));
		expect(r.verdict.key).toBe('rejected');
		expect(r.gatesPass).toBe(false);
	});

	it('marks Approved when overall ≥ 85 and gates pass', () => {
		const r = computeScores(version(['T1', 'T2', 'T3']), res({ 'PRP1-1': 'compliant', 'PRP2-1': 'compliant', 'PRP3-1': 'compliant' }));
		expect(r.overall).toBe(100);
		expect(r.verdict.key).toBe('approved');
	});

	it('treats a missing result as pending (excluded from score, blocks verdict)', () => {
		const r = computeScores(version(['T1']), res({}));
		expect(r.verdict.key).toBe('draft');
	});
});
