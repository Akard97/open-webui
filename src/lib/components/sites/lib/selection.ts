export const nextSelection = (
	sites: { id: string }[],
	removedId: string
): string | null => {
	const idx = sites.findIndex((s) => s.id === removedId);
	const remaining = sites.filter((s) => s.id !== removedId);
	if (remaining.length === 0) return null;
	if (idx === -1) return remaining[0].id;
	return remaining[Math.min(idx, remaining.length - 1)].id;
};
