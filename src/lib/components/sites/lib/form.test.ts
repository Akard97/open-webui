import { describe, expect, it } from 'vitest';
import {
	slugify,
	htmlFileNames,
	pickEntryFile,
	mergeFiles,
	grantsForLevel,
	totalSize,
	formatSize
} from './form';

describe('slugify', () => {
	it('lowercases and dashes non-alphanumerics', () => {
		expect(slugify('My Cool Page!')).toBe('my-cool-page');
	});
	it('trims leading/trailing dashes and caps at 60 chars', () => {
		expect(slugify('--Hello--')).toBe('hello');
		expect(slugify('a'.repeat(80))).toHaveLength(60);
	});
});

describe('htmlFileNames', () => {
	it('keeps .html and .htm case-insensitively', () => {
		expect(htmlFileNames(['a.HTML', 'b.htm', 'c.css', 'd.html.map'])).toEqual(['a.HTML', 'b.htm']);
	});
});

describe('pickEntryFile', () => {
	it('keeps current when still present', () => {
		expect(pickEntryFile(['a.html', 'b.html'], 'b.html')).toBe('b.html');
	});
	it('prefers index.html when current is gone', () => {
		expect(pickEntryFile(['a.html', 'index.html'], 'gone.html')).toBe('index.html');
	});
	it('falls back to first html', () => {
		expect(pickEntryFile(['a.html', 'b.html'], '')).toBe('a.html');
	});
	it('returns current unchanged when no html files', () => {
		expect(pickEntryFile([], 'x.html')).toBe('x.html');
	});
});

describe('mergeFiles', () => {
	it('appends new names, keeps first occurrence on duplicates', () => {
		const a = { name: 'a.html', v: 1 };
		expect(mergeFiles([a], [{ name: 'a.html', v: 2 } as any, { name: 'b.css', v: 3 } as any])).toEqual(
			[a, { name: 'b.css', v: 3 }]
		);
	});
});

describe('grantsForLevel', () => {
	const wild = { principal_type: 'user', principal_id: '*', permission: 'read' };
	const g = { principal_type: 'user', principal_id: 'u1', permission: 'read' };
	it('internal → single wildcard grant', () => {
		expect(grantsForLevel('internal', [g])).toEqual([wild]);
	});
	it('specific → passes grants through minus wildcard', () => {
		expect(grantsForLevel('specific', [g, wild])).toEqual([g]);
	});
	it('public and private → empty', () => {
		expect(grantsForLevel('public', [g])).toEqual([]);
		expect(grantsForLevel('private', [g])).toEqual([]);
	});
});

describe('totalSize / formatSize', () => {
	it('sums sizes, tolerating missing size', () => {
		expect(totalSize([{ size: 1000 }, {}, { size: 24 }])).toBe(1024);
	});
	it('formats B, KB, MB with one decimal', () => {
		expect(formatSize(512)).toBe('512 B');
		expect(formatSize(20172)).toBe('19.7 KB');
		expect(formatSize(3 * 1024 * 1024)).toBe('3.0 MB');
	});
});
