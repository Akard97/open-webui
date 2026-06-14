import { describe, it, expect } from 'vitest';
import { buildActiveVersion } from './seed';
import { cloneAsDraft, validateDraft, publishDraft, nextLabel } from './checklist';

describe('cloneAsDraft', () => {
	it('clones an active version into an editable draft with status draft', () => {
		const active = buildActiveVersion();
		const draft = cloneAsDraft(active);
		expect(draft.status).toBe('draft');
		expect(draft.sections).toHaveLength(active.sections.length);
		draft.sections[0].items[0].text = 'changed';
		expect(active.sections[0].items[0].text).not.toBe('changed');
	});
});

describe('validateDraft', () => {
	it('passes a well-formed draft', () => {
		const draft = cloneAsDraft(buildActiveVersion());
		expect(validateDraft(draft).ok).toBe(true);
	});

	it('fails when theme weights do not sum to 100', () => {
		const draft = cloneAsDraft(buildActiveVersion());
		draft.themes[0].weight += 5;
		const r = validateDraft(draft);
		expect(r.ok).toBe(false);
		expect(r.errors.join(' ')).toMatch(/100/);
	});

	it('fails when a theme has no items', () => {
		const draft = cloneAsDraft(buildActiveVersion());
		const emptyTheme = draft.themes[draft.themes.length - 1].id;
		draft.sections = draft.sections.filter((s) => s.theme !== emptyTheme);
		expect(validateDraft(draft).ok).toBe(false);
	});
});

describe('nextLabel', () => {
	it('bumps the minor version', () => {
		expect(nextLabel('v2.0')).toBe('v2.1');
		expect(nextLabel('v2.9')).toBe('v2.10');
	});
});

describe('publishDraft', () => {
	it('archives the old active and returns a new active version', () => {
		const active = buildActiveVersion();
		const draft = cloneAsDraft(active);
		const { versions, published } = publishDraft([active], draft, 'Head of OE');
		expect(published.status).toBe('active');
		expect(published.label).toBe('v2.1');
		expect(published.publishedBy).toBe('Head of OE');
		expect(versions.filter((v) => v.status === 'active')).toHaveLength(1);
		expect(versions.find((v) => v.id === active.id)!.status).toBe('archived');
	});
});
