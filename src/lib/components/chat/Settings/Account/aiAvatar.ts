// Pure helpers for the AI avatar dialog — kept in .ts so they're unit-testable
// (fork convention: logic in lib .ts files, .svelte stays thin).

/**
 * True when the current profile image can be reused as the generation reference:
 * a data-URL photo that isn't a generated-initials image (remote URLs like
 * gravatar or /static/user.png can't be re-uploaded without a CORS fetch).
 * `initialsImageUrls` carries every fill the app has ever generated (current and
 * legacy), so pre-rebrand default avatars are still excluded.
 */
export const isReusablePhoto = (
	profileImageUrl: string,
	initialsImageUrls: string | readonly string[]
): boolean => {
	const initialsVariants =
		typeof initialsImageUrls === 'string' ? [initialsImageUrls] : initialsImageUrls;
	return (
		typeof profileImageUrl === 'string' &&
		profileImageUrl.startsWith('data:image/') &&
		!initialsVariants.includes(profileImageUrl)
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
