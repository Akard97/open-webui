// Pure comment-tree builder — leaf module (no store/api deps) so it stays unit-testable.
import type { Comment } from './types';

export interface CommentNode {
	comment: Comment;
	children: CommentNode[];
	depth: number;
}

export type CommentSort = 'newest' | 'oldest';

/** Build a render tree from the flat fetched list. Top-level order follows `sort`;
 * replies are always chronological (oldest first). Orphans — replies whose parent
 * was hard-deleted before this fetch — are promoted to top-level, not dropped. */
export function buildCommentTree(list: Comment[], sort: CommentSort): CommentNode[] {
	const byId = new Set(list.map((c) => c.id));
	const roots: Comment[] = [];
	const kids = new Map<string, Comment[]>();
	for (const c of list) {
		if (c.parent_id && byId.has(c.parent_id)) {
			const arr = kids.get(c.parent_id) ?? [];
			arr.push(c);
			kids.set(c.parent_id, arr);
		} else {
			roots.push(c);
		}
	}
	const asc = (a: Comment, b: Comment) => a.created_at - b.created_at;
	roots.sort(sort === 'newest' ? (a, b) => b.created_at - a.created_at : asc);
	const toNode = (c: Comment, depth: number): CommentNode => ({
		comment: c,
		depth,
		children: (kids.get(c.id) ?? []).sort(asc).map((k) => toNode(k, depth + 1))
	});
	return roots.map((c) => toNode(c, 0));
}

/** Total replies in a node's subtree (for the "N replies" collapse toggle). */
export function countReplies(node: CommentNode): number {
	return node.children.reduce((sum, k) => sum + 1 + countReplies(k), 0);
}
