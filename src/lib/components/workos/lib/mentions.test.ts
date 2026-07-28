import { describe, it, expect } from 'vitest';
import { parseMentions, mentionToken, renderMentions } from './mentions';

describe('mentions', () => {
	it('parses unique ids in order', () => {
		const body = 'hi @[Lara](mention:u1) and @[Y](mention:u2) and @[Lara](mention:u1)';
		expect(parseMentions(body)).toEqual(['u1', 'u2']);
	});

	it('returns empty for none', () => {
		expect(parseMentions('plain text')).toEqual([]);
	});

	it('builds a token', () => {
		expect(mentionToken('u1', 'Lara')).toBe('@[Lara](mention:u1)');
	});

	it('renders tokens as fragment mention links', () => {
		const out = renderMentions('hi @[Felwa](mention:u1)!', () => 'Felwa');
		expect(out).toBe('hi [@Felwa](#mention-u1)!');
	});
});
