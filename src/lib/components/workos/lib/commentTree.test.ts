import { describe, expect, it } from 'vitest';
import { buildCommentTree, countReplies } from './commentTree';
import type { Comment } from './types';

const c = (id: string, at: number, parent: string | null = null): Comment =>
	({ id, task_id: 't', user_id: 'u', body: id, mentions: [], parent_id: parent,
	   created_at: at, updated_at: at }) as Comment;

describe('buildCommentTree', () => {
	it('nests replies under parents, children always oldest-first', () => {
		const tree = buildCommentTree([c('a', 1), c('b', 2, 'a'), c('c', 3, 'a'), c('d', 4, 'b')], 'oldest');
		expect(tree.map((n) => n.comment.id)).toEqual(['a']);
		expect(tree[0].children.map((n) => n.comment.id)).toEqual(['b', 'c']);
		expect(tree[0].children[0].children[0].comment.id).toBe('d');
		expect(tree[0].children[0].children[0].depth).toBe(2);
	});

	it('sorts top-level per direction, replies stay ascending', () => {
		const list = [c('a', 1), c('b', 5), c('r2', 4, 'b'), c('r1', 3, 'b')];
		expect(buildCommentTree(list, 'newest').map((n) => n.comment.id)).toEqual(['b', 'a']);
		expect(buildCommentTree(list, 'oldest').map((n) => n.comment.id)).toEqual(['a', 'b']);
		const b = buildCommentTree(list, 'newest')[0];
		expect(b.children.map((n) => n.comment.id)).toEqual(['r1', 'r2']);
	});

	it('promotes orphans (parent hard-deleted before fetch) to top-level', () => {
		const tree = buildCommentTree([c('a', 1), c('orphan', 2, 'gone')], 'oldest');
		expect(tree.map((n) => n.comment.id)).toEqual(['a', 'orphan']);
		expect(tree[1].depth).toBe(0);
	});

	it('countReplies counts the whole subtree', () => {
		const tree = buildCommentTree([c('a', 1), c('b', 2, 'a'), c('d', 4, 'b'), c('e', 5, 'd')], 'oldest');
		expect(countReplies(tree[0])).toBe(3);
	});
});
