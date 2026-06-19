// Pure client-side upload validation, mirroring the backend allowlist + size cap.
export const MAX_UPLOAD_MB = 25;
const ALLOWED = ['pdf', 'docx', 'md', 'txt'] as const;
export const ACCEPT_ATTR = ALLOWED.map((e) => `.${e}`).join(',');

function ext(name: string): string {
	const i = name.lastIndexOf('.');
	return i >= 0 ? name.slice(i + 1).toLowerCase() : '';
}

/** Returns an error message string, or null if the file is acceptable. */
export function validateUploadFile(file: File): string | null {
	if (!(ALLOWED as readonly string[]).includes(ext(file.name))) {
		return 'Unsupported file type. Upload a PDF, DOCX, MD, or TXT file.';
	}
	if (file.size <= 0) return 'The file is empty.';
	if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return `File exceeds the ${MAX_UPLOAD_MB} MB limit.`;
	return null;
}
