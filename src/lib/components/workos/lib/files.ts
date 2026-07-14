import type { WorkstreamFile } from './types';
import { formatDateShort } from './format';

// ── type classification ────────────────────────────────────────────────────
// Groups + colors mirror docs/mockups/workos-files-v1.html (approved v1).

export type FileGroup = 'img' | 'pdf' | 'doc' | 'sheet' | 'other';

export interface FileKind {
	group: FileGroup;
	color: string;
	icon: string; // Icon.svelte name for the tile glyph (unused for images)
	ext: string; // uppercase badge, e.g. 'PDF'
}

const COLOR: Record<string, string> = {
	img: '#00a5ba', pdf: '#dc2626', doc: '#2563eb', slides: '#ea580c',
	sheet: '#769a4a', zip: '#ca8a04', video: '#7c3aed', other: '#6b7280'
};

/** Chip definitions for the toolbar (All is added by the view). */
export const FILE_GROUPS: { id: FileGroup; label: string; dot: string }[] = [
	{ id: 'img', label: 'Images', dot: COLOR.img },
	{ id: 'pdf', label: 'PDFs', dot: COLOR.pdf },
	{ id: 'doc', label: 'Docs', dot: COLOR.doc },
	{ id: 'sheet', label: 'Sheets', dot: COLOR.sheet },
	{ id: 'other', label: 'Other', dot: COLOR.zip }
];

/** ext → [group, color key, icon] — pptx keeps its slide color inside the doc group. */
const EXT: Record<string, [FileGroup, string, string]> = {
	jpg: ['img', 'img', 'image'], jpeg: ['img', 'img', 'image'], png: ['img', 'img', 'image'],
	gif: ['img', 'img', 'image'], webp: ['img', 'img', 'image'], svg: ['img', 'img', 'image'],
	pdf: ['pdf', 'pdf', 'file-text'],
	doc: ['doc', 'doc', 'file-text'], docx: ['doc', 'doc', 'file-text'],
	txt: ['doc', 'doc', 'file-text'], md: ['doc', 'doc', 'file-text'], json: ['doc', 'doc', 'file-text'],
	ppt: ['doc', 'slides', 'presentation'], pptx: ['doc', 'slides', 'presentation'],
	xls: ['sheet', 'sheet', 'file-spreadsheet'], xlsx: ['sheet', 'sheet', 'file-spreadsheet'],
	csv: ['sheet', 'sheet', 'file-spreadsheet'],
	zip: ['other', 'zip', 'archive'],
	mp4: ['other', 'video', 'play-circle'], mov: ['other', 'video', 'play-circle'],
	webm: ['other', 'video', 'play-circle']
};

export function fileKind(name: string, contentType?: string | null): FileKind {
	const dot = name.lastIndexOf('.');
	const ext = dot > 0 ? name.slice(dot + 1).toLowerCase() : '';
	if (contentType?.startsWith('image/')) {
		return { group: 'img', color: COLOR.img, icon: 'image', ext: ext ? ext.toUpperCase() : 'IMG' };
	}
	const hit = EXT[ext];
	if (hit) return { group: hit[0], color: COLOR[hit[1]], icon: hit[2], ext: ext.toUpperCase() };
	return { group: 'other', color: COLOR.other, icon: 'file', ext: ext ? ext.toUpperCase() : 'FILE' };
}

/** True when the browser can render the attachment as an <img> thumbnail. */
export function isImage(f: WorkstreamFile): boolean {
	return !!f.content_type && f.content_type.startsWith('image/');
}

// ── formatting ─────────────────────────────────────────────────────────────

/** '900 B' / '342 KB' / '3.2 MB' — mirrors the mockup's size column. */
export function formatBytes(n: number): string {
	if (n >= 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
	if (n >= 1024) return `${Math.round(n / 1024)} KB`;
	return `${n} B`;
}

// ── recency grouping ───────────────────────────────────────────────────────

export type RecencyBucket = 'today' | 'week' | 'earlier';

export function recencyBucket(ts: number, now: number): RecencyBucket {
	const d = new Date(ts);
	const n = new Date(now);
	if (
		d.getFullYear() === n.getFullYear() && d.getMonth() === n.getMonth() && d.getDate() === n.getDate()
	) return 'today';
	if (now - ts < 7 * 86_400_000) return 'week';
	return 'earlier';
}

/** Today → '09:30 AM'; this week → 'Mon 09:30 AM'; earlier → 'Jun 1'. */
export function formatFileDate(ts: number, now: number): string {
	const bucket = recencyBucket(ts, now);
	const d = new Date(ts);
	const time = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
	if (bucket === 'today') return time;
	if (bucket === 'week') return `${d.toLocaleDateString('en-US', { weekday: 'short' })} ${time}`;
	return formatDateShort(ts);
}

export interface FileBucket {
	id: RecencyBucket;
	label: string;
	rows: WorkstreamFile[];
}

const BUCKET_LABEL: Record<RecencyBucket, string> = {
	today: 'Today', week: 'This week', earlier: 'Earlier'
};

/** Non-empty buckets in today → week → earlier order, preserving input order. */
export function bucketFiles(files: WorkstreamFile[], now: number): FileBucket[] {
	const order: RecencyBucket[] = ['today', 'week', 'earlier'];
	return order
		.map((id) => ({ id, label: BUCKET_LABEL[id], rows: files.filter((f) => recencyBucket(f.created_at, now) === id) }))
		.filter((b) => b.rows.length > 0);
}

// ── filter / sort / counts ─────────────────────────────────────────────────

export type FileSort = 'newest' | 'name' | 'size';

export const FILE_SORT_LABEL: Record<FileSort, string> = {
	newest: 'Newest', name: 'Name', size: 'Size'
};

export function sortFiles(files: WorkstreamFile[], sort: FileSort): WorkstreamFile[] {
	const out = [...files];
	if (sort === 'name') out.sort((a, b) => a.name.localeCompare(b.name));
	else if (sort === 'size') out.sort((a, b) => b.size - a.size);
	else out.sort((a, b) => b.created_at - a.created_at);
	return out;
}

export function filterFiles(files: WorkstreamFile[], group: FileGroup | 'all', query: string): WorkstreamFile[] {
	const q = query.trim().toLowerCase();
	return files.filter(
		(f) =>
			(group === 'all' || fileKind(f.name, f.content_type).group === group) &&
			(!q || f.name.toLowerCase().includes(q))
	);
}

export function groupCounts(files: WorkstreamFile[]): Record<FileGroup | 'all', number> {
	const out: Record<FileGroup | 'all', number> = { all: files.length, img: 0, pdf: 0, doc: 0, sheet: 0, other: 0 };
	for (const f of files) out[fileKind(f.name, f.content_type).group] += 1;
	return out;
}
