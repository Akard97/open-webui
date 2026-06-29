import { describe, expect, it } from 'vitest';
import { defaultColumnPrefs, parseColumnPrefs, gridTemplate, LIST_COLUMNS } from './columns';

describe('LIST_COLUMNS', () => {
	it('lists the five optional columns in fixed order', () => {
		expect(LIST_COLUMNS.map((c) => c.key)).toEqual(['assignee', 'due', 'priority', 'labels', 'progress']);
	});
});

describe('defaultColumnPrefs', () => {
	it('enables every optional column', () => {
		expect(defaultColumnPrefs()).toEqual({
			assignee: true, due: true, priority: true, labels: true, progress: true
		});
	});
});

describe('parseColumnPrefs', () => {
	it('returns defaults for null', () => {
		expect(parseColumnPrefs(null)).toEqual(defaultColumnPrefs());
	});
	it('returns defaults for invalid JSON', () => {
		expect(parseColumnPrefs('not json')).toEqual(defaultColumnPrefs());
	});
	it('merges a partial object over defaults', () => {
		expect(parseColumnPrefs('{"labels":false,"progress":false}')).toEqual({
			assignee: true, due: true, priority: true, labels: false, progress: false
		});
	});
	it('ignores unknown keys and non-boolean values', () => {
		expect(parseColumnPrefs('{"bogus":true,"assignee":"yes"}')).toEqual(defaultColumnPrefs());
	});
});

describe('gridTemplate', () => {
	it('builds name + all columns + menu when everything is visible', () => {
		expect(gridTemplate(defaultColumnPrefs())).toBe(
			'minmax(180px, 1fr) 120px 120px 130px 160px 120px 36px'
		);
	});
	it('omits hidden columns but keeps name and menu', () => {
		expect(gridTemplate({ assignee: true, due: true, priority: true, labels: false, progress: false })).toBe(
			'minmax(180px, 1fr) 120px 120px 130px 36px'
		);
	});
});
