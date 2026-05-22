// Pure helpers for the Policy Library view.
// All functions here are side-effect-free and unit-tested in library.test.ts.

import type { LibraryPolicy } from './types';

/** A policy is "fresh" if it was updated within the last 7 days. */
export function isFresh(updatedDays: number | null | undefined): boolean {
	return typeof updatedDays === 'number' && updatedDays >= 0 && updatedDays <= 7;
}

export interface PolicyFilter {
	query: string;
	fn: string; // function id or 'all'
}

/** Apply search + function filter to a list of policies. */
export function filterPolicies(policies: LibraryPolicy[], f: PolicyFilter): LibraryPolicy[] {
	const q = f.query.trim().toLowerCase();
	return policies.filter((p) => {
		if (f.fn !== 'all' && p.fn !== f.fn) return false;
		if (!q) return true;
		return (
			p.title.toLowerCase().includes(q) ||
			p.code.toLowerCase().includes(q) ||
			p.owner.toLowerCase().includes(q)
		);
	});
}

export interface FunctionGroup {
	fn: string;
	name: string;
	policies: LibraryPolicy[];
}

/**
 * Group policies by `fn` and return groups ordered by policy count desc.
 * Policies within a group are sorted by `updatedDays` asc (fresh first).
 * Empty groups are dropped.
 */
export function groupByFunctionDesc(
	policies: LibraryPolicy[],
	fnMeta: Record<string, { name: string }>
): FunctionGroup[] {
	const byFn = new Map<string, LibraryPolicy[]>();
	for (const p of policies) {
		const list = byFn.get(p.fn) ?? [];
		list.push(p);
		byFn.set(p.fn, list);
	}
	const groups: FunctionGroup[] = [];
	for (const [fn, list] of byFn.entries()) {
		const meta = fnMeta[fn];
		if (!meta) continue;
		const sorted = list.slice().sort((a, b) => (a.updatedDays ?? 99999) - (b.updatedDays ?? 99999));
		groups.push({ fn, name: meta.name, policies: sorted });
	}
	groups.sort((a, b) => b.policies.length - a.policies.length);
	return groups;
}

/**
 * Return the top N most recently updated policies. Prefers policies updated
 * within `windowDays`; if fewer than N exist in that window, falls back to
 * the top N regardless of recency (so the strip always renders if data exists).
 */
export function recentlyUpdated(
	policies: LibraryPolicy[],
	n: number,
	windowDays: number
): LibraryPolicy[] {
	const sorted = policies
		.slice()
		.sort((a, b) => (a.updatedDays ?? 99999) - (b.updatedDays ?? 99999));
	const inWindow = sorted.filter((p) => (p.updatedDays ?? 99999) <= windowDays);
	return (inWindow.length >= n ? inWindow : sorted).slice(0, n);
}
