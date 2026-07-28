// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { bodyToEditorHtml, mentionChipHtml, serializeEditor } from './richText';

function editorWith(html: string): HTMLElement {
	const el = document.createElement('div');
	el.innerHTML = html;
	return el;
}

describe('serializeEditor', () => {
	it('serializes text and chips to the wire token format', () => {
		const el = editorWith(`hello ${mentionChipHtml('u1', 'Felwa')} world`);
		expect(serializeEditor(el)).toBe('hello @[Felwa](mention:u1) world');
	});

	it('turns BR and block elements into newlines', () => {
		const el = editorWith('line1<br>line2<div>line3</div>');
		expect(serializeEditor(el)).toBe('line1\nline2\nline3');
	});

	it('round-trips: bodyToEditorHtml then serializeEditor is identity', () => {
		const body = 'ping @[Noah Pierre](mention:u7) check\nsecond line';
		expect(serializeEditor(editorWith(bodyToEditorHtml(body)))).toBe(body);
	});

	it('escapes HTML in plain text (no injection through bodyToEditorHtml)', () => {
		const html = bodyToEditorHtml('<img src=x onerror=alert(1)>');
		expect(html).not.toContain('<img');
		const el = editorWith(html);
		expect(serializeEditor(el)).toBe('<img src=x onerror=alert(1)>');
	});
});
