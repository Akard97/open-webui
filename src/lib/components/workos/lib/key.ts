const STEP = 1000;
const MIN_GAP = 1e-4;

/** sort_key for a card dropped between `before` and `after` (either may be null at an edge). */
export function midpoint(before: number | null, after: number | null): number {
	if (before == null && after == null) return STEP;
	if (before == null) return (after as number) / 2;
	if (after == null) return before + STEP;
	return (before + after) / 2;
}

/** True if any two adjacent keys are closer than MIN_GAP (float precision risk). */
export function needsRebalance(keys: number[]): boolean {
	for (let i = 1; i < keys.length; i++) {
		if (Math.abs(keys[i] - keys[i - 1]) < MIN_GAP) return true;
	}
	return false;
}

/** Evenly spaced ascending keys for `count` items. */
export function rebalance(count: number): number[] {
	return Array.from({ length: count }, (_, i) => (i + 1) * STEP);
}

export function parseKey(key: string): { prefix: string; number: number } | null {
	const m = /^([A-Za-z]+)-(\d+)$/.exec(key);
	return m ? { prefix: m[1], number: parseInt(m[2], 10) } : null;
}
