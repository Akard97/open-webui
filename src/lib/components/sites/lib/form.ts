import { isEveryoneGrant } from './access';

export const slugify = (v: string): string =>
	v
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '')
		.slice(0, 60);

export const htmlFileNames = (names: string[]): string[] =>
	names.filter((n) => /\.html?$/i.test(n));

export const pickEntryFile = (htmlNames: string[], current: string): string => {
	if (htmlNames.length === 0 || htmlNames.includes(current)) return current;
	return htmlNames.includes('index.html') ? 'index.html' : htmlNames[0];
};

export const mergeFiles = <T extends { name: string }>(existing: T[], incoming: T[]): T[] => {
	const next = [...existing];
	for (const f of incoming) {
		if (!next.some((x) => x.name === f.name)) next.push(f);
	}
	return next;
};

export type StagedFileStatus = 'new' | 'replace';

export const diffFiles = <C extends { name: string }, S extends { name: string }>(
	current: C[],
	staged: S[]
): { published: { file: S; status: StagedFileStatus }[]; removed: C[] } => {
	// An empty staged set means "keep the current files" (the backend only
	// replaces files when new ones are uploaded), so nothing is removed.
	if (staged.length === 0) return { published: [], removed: [] };
	const currentNames = new Set(current.map((f) => f.name));
	const stagedNames = new Set(staged.map((f) => f.name));
	return {
		published: staged.map((file) => ({
			file,
			status: currentNames.has(file.name) ? 'replace' : 'new'
		})),
		removed: current.filter((f) => !stagedNames.has(f.name))
	};
};

const IMAGE_EXTS = new Set(['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'ico', 'avif', 'bmp']);

export const fileTile = (name: string): { label: string; kind: 'html' | 'image' | 'other' } => {
	const dot = name.lastIndexOf('.');
	const ext = dot > 0 ? name.slice(dot + 1).toLowerCase() : '';
	if (!ext) return { label: 'file', kind: 'other' };
	const kind = ext === 'html' || ext === 'htm' ? 'html' : IMAGE_EXTS.has(ext) ? 'image' : 'other';
	return { label: ext.slice(0, 4), kind };
};

export const grantsForLevel = (level: string, specificGrants: any[]): any[] => {
	if (level === 'internal')
		return [{ principal_type: 'user', principal_id: '*', permission: 'read' }];
	if (level === 'specific') return specificGrants.filter((g) => !isEveryoneGrant(g));
	return [];
};

export const totalSize = (files: { size?: number }[]): number =>
	files.reduce((acc, f) => acc + (f.size ?? 0), 0);

export const formatSize = (bytes: number): string => {
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
	return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};
