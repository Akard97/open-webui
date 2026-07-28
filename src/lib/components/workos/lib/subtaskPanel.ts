import type { Subtask } from './types';

/** Gap between renumbered keys; also the step past either end of the list. */
export const SORT_SPACING = 1000;

export interface SortKeyUpdate {
	id: string;
	sort_key: number;
}

/**
 * Plan the sort_key writes for moving list[fromIndex] to final position toIndex.
 * `list` must already be sorted by sort_key ascending; never mutated.
 * Normal case: a single midpoint update. Degenerate midpoint (float precision /
 * duplicate keys): full-list renumber to (index+1)*SORT_SPACING. No-op or
 * invalid indices: empty array.
 */
export function computeSortKey(
	list: Pick<Subtask, 'id' | 'sort_key'>[],
	fromIndex: number,
	toIndex: number
): SortKeyUpdate[] {
	if (fromIndex === toIndex) return [];
	if (fromIndex < 0 || toIndex < 0 || fromIndex >= list.length || toIndex >= list.length) return [];

	const moved = list[fromIndex];
	const rest = list.filter((_, i) => i !== fromIndex);
	const prev = rest[toIndex - 1];
	const next = rest[toIndex];

	let key: number;
	if (!prev && !next) return [];
	else if (!prev) key = next.sort_key - SORT_SPACING;
	else if (!next) key = prev.sort_key + SORT_SPACING;
	else key = (prev.sort_key + next.sort_key) / 2;

	const collides = (prev && !(key > prev.sort_key)) || (next && !(key < next.sort_key));
	if (!collides) return [{ id: moved.id, sort_key: key }];

	const finalOrder = [...rest.slice(0, toIndex), moved, ...rest.slice(toIndex)];
	return finalOrder.map((s, i) => ({ id: s.id, sort_key: (i + 1) * SORT_SPACING }));
}

/**
 * Inline height for an autogrow textarea. A hidden element (e.g. mounted under
 * an inactive tab) measures scrollHeight 0 — return '' so the inline style is
 * cleared and the browser's natural height applies once it becomes visible.
 */
export function autogrowHeight(scrollHeight: number): string {
	return scrollHeight > 0 ? `${scrollHeight}px` : '';
}

export type RenameResolution = { action: 'commit'; title: string } | { action: 'revert' };

/** Decide what an inline-rename blur/Enter should do. */
export function resolveRename(current: string, draft: string): RenameResolution {
	const title = draft.trim();
	if (!title || title === current) return { action: 'revert' };
	return { action: 'commit', title };
}
