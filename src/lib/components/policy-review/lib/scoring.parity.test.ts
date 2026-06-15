import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { computeScores } from './scoring';
import type { ChecklistVersion } from './types';

const fixtures = JSON.parse(
	readFileSync(
		resolve('backend/open_webui/test/policy_review/policy_scoring_fixtures.json'),
		'utf-8'
	)
) as Array<{
	name: string;
	definition: Partial<ChecklistVersion>;
	results: Record<string, { result: string }>;
	expected: { overall: number; gatesPass: boolean; humanItemsRemain: boolean; verdictKey: string };
}>;

describe('scoring parity with backend fixtures', () => {
	for (const c of fixtures) {
		it(c.name, () => {
			const r = computeScores(c.definition as ChecklistVersion, c.results as never);
			expect(r.overall).toBe(c.expected.overall);
			expect(r.gatesPass).toBe(c.expected.gatesPass);
			expect(r.humanItemsRemain).toBe(c.expected.humanItemsRemain);
			expect(r.verdict.key).toBe(c.expected.verdictKey);
		});
	}
});
