import { describe, it, expect } from 'vitest';
import {
	fileKind, formatBytes, recencyBucket, formatFileDate,
	bucketFiles, sortFiles, filterFiles, groupCounts
} from './files';
import type { WorkstreamFile } from './types';

const mk = (over: Partial<WorkstreamFile>): WorkstreamFile => ({
	id: 'a1', task_id: 't1', comment_id: null, storage_key: 'k', name: 'file.txt',
	size: 10, content_type: 'text/plain', created_by_id: 'u1', created_at: 0,
	task_key: 'OSL-1', task_title: 'T', task_status: 'todo', ...over
});

describe('fileKind', () => {
	it('classifies images by content type regardless of extension', () => {
		expect(fileKind('shot', 'image/png').group).toBe('img');
	});
	it('classifies by extension', () => {
		expect(fileKind('a.pdf', null).group).toBe('pdf');
		expect(fileKind('a.docx', null).group).toBe('doc');
		expect(fileKind('a.pptx', null).group).toBe('doc');
		expect(fileKind('a.xlsx', null).group).toBe('sheet');
		expect(fileKind('a.csv', null).group).toBe('sheet');
		expect(fileKind('a.zip', null).group).toBe('other');
	});
	it('uppercases the extension badge and falls back to FILE', () => {
		expect(fileKind('a.pdf', null).ext).toBe('PDF');
		expect(fileKind('noext', null).ext).toBe('FILE');
	});
	it('unknown extension → other', () => {
		expect(fileKind('a.xyz', null).group).toBe('other');
	});
});

describe('formatBytes', () => {
	it('formats B / KB / MB like the mockup', () => {
		expect(formatBytes(900)).toBe('900 B');
		expect(formatBytes(342 * 1024)).toBe('342 KB');
		expect(formatBytes(3.2 * 1024 * 1024)).toBe('3.2 MB');
	});
});

describe('recencyBucket', () => {
	// now = 2026-07-14T12:00 local
	const now = new Date(2026, 6, 14, 12, 0).getTime();
	it('same local day → today', () => {
		expect(recencyBucket(new Date(2026, 6, 14, 0, 5).getTime(), now)).toBe('today');
	});
	it('yesterday → week', () => {
		expect(recencyBucket(new Date(2026, 6, 13, 23, 0).getTime(), now)).toBe('week');
	});
	it('6 days ago → week, 8 days ago → earlier', () => {
		expect(recencyBucket(new Date(2026, 6, 8, 12, 0).getTime(), now)).toBe('week');
		expect(recencyBucket(new Date(2026, 6, 6, 12, 0).getTime(), now)).toBe('earlier');
	});
});

describe('formatFileDate', () => {
	const now = new Date(2026, 6, 14, 12, 0).getTime();
	it('today → time only; week → weekday + time; earlier → short date', () => {
		expect(formatFileDate(new Date(2026, 6, 14, 9, 30).getTime(), now)).toMatch(/9:30/);
		expect(formatFileDate(new Date(2026, 6, 13, 9, 30).getTime(), now)).toMatch(/^Mon/);
		expect(formatFileDate(new Date(2026, 5, 1).getTime(), now)).toBe('Jun 1');
	});
});

describe('bucketFiles / sortFiles / filterFiles / groupCounts', () => {
	const now = new Date(2026, 6, 14, 12, 0).getTime();
	const files = [
		mk({ id: 'a', name: 'zeta.pdf', size: 5, created_at: new Date(2026, 6, 14, 9, 0).getTime() }),
		mk({ id: 'b', name: 'alpha.png', content_type: 'image/png', size: 50, created_at: new Date(2026, 6, 12).getTime() }),
		mk({ id: 'c', name: 'mid.xlsx', size: 20, created_at: new Date(2026, 5, 1).getTime() })
	];
	it('buckets only non-empty groups in today/week/earlier order', () => {
		const buckets = bucketFiles(files, now);
		expect(buckets.map((b) => b.id)).toEqual(['today', 'week', 'earlier']);
		expect(buckets[0].rows.map((r) => r.id)).toEqual(['a']);
		expect(bucketFiles([files[0]], now).map((b) => b.id)).toEqual(['today']);
	});
	it('sorts newest / name / size without mutating input', () => {
		expect(sortFiles(files, 'newest').map((f) => f.id)).toEqual(['a', 'b', 'c']);
		expect(sortFiles(files, 'name').map((f) => f.id)).toEqual(['b', 'c', 'a']);
		expect(sortFiles(files, 'size').map((f) => f.id)).toEqual(['b', 'c', 'a']);
		expect(files.map((f) => f.id)).toEqual(['a', 'b', 'c']);
	});
	it('filters by group and by name substring (case-insensitive)', () => {
		expect(filterFiles(files, 'img', '').map((f) => f.id)).toEqual(['b']);
		expect(filterFiles(files, 'all', 'ZETA').map((f) => f.id)).toEqual(['a']);
	});
	it('counts per group plus all', () => {
		const c = groupCounts(files);
		expect(c.all).toBe(3);
		expect(c.img).toBe(1);
		expect(c.pdf).toBe(1);
		expect(c.sheet).toBe(1);
		expect(c.doc).toBe(0);
	});
});
