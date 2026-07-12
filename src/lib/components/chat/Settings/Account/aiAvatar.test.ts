import { describe, it, expect } from 'vitest';
import { isReusablePhoto, dataUrlToBlob } from './aiAvatar';

const INITIALS = 'data:image/png;base64,aW5pdGlhbHM=';
const LEGACY_INITIALS = 'data:image/png;base64,bGVnYWN5';

describe('isReusablePhoto', () => {
	it('accepts an uploaded data-URL photo', () => {
		expect(isReusablePhoto('data:image/webp;base64,Zm9v', INITIALS)).toBe(true);
		expect(isReusablePhoto('data:image/webp;base64,Zm9v', [INITIALS, LEGACY_INITIALS])).toBe(true);
	});
	it('rejects the generated-initials image', () => {
		expect(isReusablePhoto(INITIALS, INITIALS)).toBe(false);
		expect(isReusablePhoto(INITIALS, [INITIALS, LEGACY_INITIALS])).toBe(false);
	});
	it('rejects legacy-fill initials images stored before the rebrand', () => {
		expect(isReusablePhoto(LEGACY_INITIALS, [INITIALS, LEGACY_INITIALS])).toBe(false);
	});
	it('rejects remote URLs, the default image, and empty values', () => {
		expect(isReusablePhoto('https://example.com/a.png', INITIALS)).toBe(false);
		expect(isReusablePhoto('/static/user.png', INITIALS)).toBe(false);
		expect(isReusablePhoto('', INITIALS)).toBe(false);
		expect(isReusablePhoto('', [INITIALS, LEGACY_INITIALS])).toBe(false);
	});
});

describe('dataUrlToBlob', () => {
	it('decodes mime type and bytes', async () => {
		const blob = dataUrlToBlob('data:image/webp;base64,' + btoa('hello'));
		expect(blob.type).toBe('image/webp');
		expect(await blob.text()).toBe('hello');
	});
	it('falls back to octet-stream for a bare data URL', () => {
		const blob = dataUrlToBlob('data:;base64,' + btoa('x'));
		expect(blob.type).toBe('application/octet-stream');
	});
});
