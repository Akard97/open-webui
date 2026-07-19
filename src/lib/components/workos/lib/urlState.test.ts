import { describe, it, expect } from 'vitest';
import { buildQuery, parseQuery, decideOp, WORKSTREAM_VIEWS, type NavState } from './urlState';

const st = (over: Partial<NavState> = {}): NavState => ({
	view: 'mywork', ws: null, task: null, ...over
});

describe('buildQuery', () => {
	it('empty for the default view with nothing open', () => {
		expect(buildQuery(st())).toBe('');
	});
	it('omits view=mywork but keeps task', () => {
		expect(buildQuery(st({ task: 't1' }))).toBe('?task=t1');
	});
	it('serializes view + ws + task in fixed order', () => {
		expect(buildQuery(st({ view: 'board', ws: 'w1', task: 't1' }))).toBe('?view=board&ws=w1&task=t1');
	});
	it('drops ws for global views even when a workstream is selected', () => {
		expect(buildQuery(st({ view: 'inbox', ws: 'w1' }))).toBe('?view=inbox');
		expect(buildQuery(st({ view: 'mywork', ws: 'w1' }))).toBe('');
	});
	it('workstream views carry ws', () => {
		for (const v of WORKSTREAM_VIEWS) {
			expect(buildQuery(st({ view: v, ws: 'w1' }))).toBe(`?view=${v}&ws=w1`);
		}
	});
});

describe('parseQuery', () => {
	const parse = (s: string) => parseQuery(new URLSearchParams(s));
	it('empty → mywork', () => {
		expect(parse('')).toEqual(st());
	});
	it('round-trips a full board state', () => {
		expect(parse('view=board&ws=w1&task=t1')).toEqual(st({ view: 'board', ws: 'w1', task: 't1' }));
	});
	it('unknown view → mywork, ws dropped', () => {
		expect(parse('view=bogus')).toEqual(st());
	});
	it('bare ws with no view implies board', () => {
		expect(parse('ws=w1')).toEqual(st({ view: 'board', ws: 'w1' }));
	});
	it('unknown view with ws also implies board (ws wins over garbage)', () => {
		expect(parse('view=bogus&ws=w1')).toEqual(st({ view: 'board', ws: 'w1' }));
	});
	it('global view ignores a stray ws param', () => {
		expect(parse('view=inbox&ws=w1')).toEqual(st({ view: 'inbox' }));
	});
	it('task survives on any view', () => {
		expect(parse('task=t9')).toEqual(st({ task: 't9' }));
		expect(parse('view=inbox&task=t9')).toEqual(st({ view: 'inbox', task: 't9' }));
	});
});

describe('decideOp', () => {
	it('view change → push', () => {
		expect(decideOp(st(), st({ view: 'inbox' }))).toBe('push');
	});
	it('ws change → push (even with a task change riding along)', () => {
		expect(decideOp(st({ view: 'board', ws: 'w1', task: 't1' }), st({ view: 'board', ws: 'w2' }))).toBe('push');
	});
	it('task-only change → replace (open and close)', () => {
		expect(decideOp(st({ view: 'board', ws: 'w1' }), st({ view: 'board', ws: 'w1', task: 't1' }))).toBe('replace');
		expect(decideOp(st({ view: 'board', ws: 'w1', task: 't1' }), st({ view: 'board', ws: 'w1' }))).toBe('replace');
	});
	it('no change → none', () => {
		const a = st({ view: 'list', ws: 'w1', task: 't1' });
		expect(decideOp(a, { ...a })).toBe('none');
	});
});
