// Rotating palette shared by user avatars and freshly created tags — a pure
// leaf module (no store/api deps) so it stays trivially unit-testable and
// store.ts can import it without creating a cycle.
export const LABEL_PALETTE = ['#00a5ba', '#769a4a', '#d97706', '#dc2626', '#7c3aed', '#0ea5e9', '#db2777', '#ca8a04'];

// Same hash as the legacy per-workstream Avatar component (h = h*31 + charCode, |0, abs)
// so migrating call sites doesn't shuffle colors for existing users.
function hash(s: string): number {
	let h = 0;
	for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
	return Math.abs(h);
}

/** Deterministic hash of a user id/name into LABEL_PALETTE — stable across renders. */
export function avatarColor(idOrName: string): string {
	return LABEL_PALETTE[hash(idOrName) % LABEL_PALETTE.length];
}
