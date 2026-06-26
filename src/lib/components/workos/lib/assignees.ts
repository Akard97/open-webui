/** Toggle a user id within a task's assignee list (pure; never mutates the input). */
export function toggleAssignee(ids: string[] | null | undefined, id: string): string[] {
	const current = ids ?? [];
	return current.includes(id) ? current.filter((x) => x !== id) : [...current, id];
}
