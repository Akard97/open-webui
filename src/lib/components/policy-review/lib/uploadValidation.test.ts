import { describe, it, expect } from 'vitest';
import { validateUploadFile, MAX_UPLOAD_MB, ACCEPT_ATTR } from './uploadValidation';

function file(name: string, sizeBytes: number, type = '') {
	const f = new File([new Uint8Array(1)], name, { type });
	Object.defineProperty(f, 'size', { value: sizeBytes });
	return f;
}

describe('validateUploadFile', () => {
	it('accepts pdf/docx/md/txt', () => {
		expect(validateUploadFile(file('a.pdf', 100))).toBeNull();
		expect(validateUploadFile(file('a.DOCX', 100))).toBeNull();
		expect(validateUploadFile(file('a.md', 100))).toBeNull();
		expect(validateUploadFile(file('a.txt', 100))).toBeNull();
	});

	it('rejects unsupported types', () => {
		expect(validateUploadFile(file('a.png', 100))).toMatch(/PDF, DOCX, MD, or TXT/);
	});

	it('rejects empty files', () => {
		expect(validateUploadFile(file('a.pdf', 0))).toMatch(/empty/i);
	});

	it('rejects oversize files', () => {
		expect(validateUploadFile(file('a.pdf', MAX_UPLOAD_MB * 1024 * 1024 + 1))).toMatch(/limit/i);
	});

	it('exposes an accept attribute string', () => {
		expect(ACCEPT_ATTR).toContain('.pdf');
		expect(ACCEPT_ATTR).toContain('.txt');
	});
});
