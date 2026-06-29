import { describe, expect, it } from 'vitest';
import { statusShape } from './colors';

describe('statusShape', () => {
	it('maps each status to its board glyph shape', () => {
		expect(statusShape('backlog')).toBe('dashed');
		expect(statusShape('todo')).toBe('ring');
		expect(statusShape('in_progress')).toBe('half');
		expect(statusShape('in_review')).toBe('half');
		expect(statusShape('done')).toBe('check');
		expect(statusShape('canceled')).toBe('x');
	});
});
