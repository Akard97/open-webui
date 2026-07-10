// Rotating palette for freshly created tags — a pure leaf module (no store/api deps)
// so it stays trivially unit-testable and store.ts can import it without creating a cycle.
export const LABEL_PALETTE = ['#00a5ba', '#769a4a', '#d97706', '#dc2626', '#7c3aed', '#0ea5e9', '#db2777', '#ca8a04'];

export type AvatarColors = Readonly<{ background: string; foreground: string }>;

export const AVATAR_BACKGROUNDS = [
	'#00313f',
	'#026c80',
	'#00a5ba',
	'#769a4a',
	'#dfa244',
	'#c96b5d',
	'#54c2d1',
	'#a4c979'
] as const;

const BRAND_FOREGROUNDS = ['#ffffff', '#00313f'] as const;

function relativeLuminance(hex: string): number {
	const channels = hex
		.slice(1)
		.match(/.{2}/g)!
		.map((part) => parseInt(part, 16) / 255);
	const linear = channels.map((value) =>
		value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
	);
	return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrastRatio(a: string, b: string): number {
	const [lighter, darker] = [relativeLuminance(a), relativeLuminance(b)].sort(
		(x, y) => y - x
	);
	return (lighter + 0.05) / (darker + 0.05);
}

function foregroundFor(background: string): string {
	let strongest = BRAND_FOREGROUNDS[0];
	let strongestRatio = contrastRatio(background, strongest);

	for (const candidate of BRAND_FOREGROUNDS.slice(1)) {
		const ratio = contrastRatio(background, candidate);
		if (ratio > strongestRatio) {
			strongest = candidate;
			strongestRatio = ratio;
		}
	}

	return strongestRatio >= 4.5 ? strongest : '#000000';
}

export const AVATAR_PALETTE: readonly AvatarColors[] = AVATAR_BACKGROUNDS.map(
	(background) => ({ background, foreground: foregroundFor(background) })
);

// Same hash as the legacy per-workstream Avatar component (h = h*31 + charCode, |0, abs)
// so migrating call sites preserves each existing user's palette index.
function hash(s: string): number {
	let h = 0;
	for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
	return Math.abs(h);
}

/** Deterministic hash of a user id/name into AVATAR_PALETTE — stable across renders. */
export function avatarColors(idOrName: string): AvatarColors {
	return AVATAR_PALETTE[hash(idOrName) % AVATAR_PALETTE.length];
}

/** Background-only compatibility wrapper for avatar consumers. */
export function avatarColor(idOrName: string): string {
	return avatarColors(idOrName).background;
}
