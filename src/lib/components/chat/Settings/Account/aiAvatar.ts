// Pure helpers for the AI avatar dialog — kept in .ts so they're unit-testable
// (fork convention: logic in lib .ts files, .svelte stays thin).

/**
 * True when the current profile image can be reused as the generation reference:
 * a data-URL photo that isn't the generated-initials image (remote URLs like
 * gravatar or /static/user.png can't be re-uploaded without a CORS fetch).
 */
export const isReusablePhoto = (
	profileImageUrl: string,
	initialsImageUrl: string
): boolean => {
	return (
		typeof profileImageUrl === 'string' &&
		profileImageUrl.startsWith('data:image/') &&
		profileImageUrl !== initialsImageUrl
	);
};

/** Convert a data URL into a Blob for multipart upload. */
export const dataUrlToBlob = (dataUrl: string): Blob => {
	const [head, b64] = dataUrl.split(',');
	const mime = head.match(/data:(.*?);base64/)?.[1] || 'application/octet-stream';
	const bytes = atob(b64);
	const arr = new Uint8Array(bytes.length);
	for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
	return new Blob([arr], { type: mime });
};
