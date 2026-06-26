import { describe, it, expect } from 'vitest';
import { toggleAssignee } from './assignees';

describe('toggleAssignee', () => {
	it('adds an id that is not present', () => {
		expect(toggleAssignee(['u1'], 'u2')).toEqual(['u1', 'u2']);
	});
	it('removes an id that is present', () => {
		expect(toggleAssignee(['u1', 'u2'], 'u1')).toEqual(['u2']);
	});
	it('treats undefined/null current list as empty', () => {
		expect(toggleAssignee(undefined, 'u1')).toEqual(['u1']);
		expect(toggleAssignee(null, 'u1')).toEqual(['u1']);
	});
	it('does not mutate the input array', () => {
		const input = ['u1'];
		toggleAssignee(input, 'u2');
		expect(input).toEqual(['u1']);
	});
});
