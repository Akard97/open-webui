import type { AccessTeamOverview, Member } from './types';

// Pure helpers for the Access console. The server stays the authority on every
// rule mirrored here (last-owner guard, membership checks); these only shape
// the UI (search, picker candidates, pre-emptively disabled controls).

export function filterOverview(rows: AccessTeamOverview[], query: string): AccessTeamOverview[] {
	const q = query.trim().toLowerCase();
	if (!q) return rows;
	return rows.filter(
		(r) =>
			r.team.name.toLowerCase().includes(q) ||
			r.team.key.toLowerCase().includes(q) ||
			r.workspaces.some((w) => w.name.toLowerCase().includes(q))
	);
}

// App users not yet on the team — candidates for the team add-member picker.
export function addableUsers(
	roster: { id: string; name: string }[],
	members: Member[]
): { id: string; name: string }[] {
	const existing = new Set(members.map((m) => m.user_id));
	return roster.filter((u) => !existing.has(u.id));
}

// Team members not yet on the restricted workspace — candidates for the
// workspace add-member picker. Sourced from the team (never the app roster):
// the backend does not validate the target is a team member, so the UI
// enforces the sane subset.
export function addableWorkspaceMembers(teamMembers: Member[], wsMembers: Member[]): Member[] {
	const existing = new Set(wsMembers.map((m) => m.user_id));
	return teamMembers.filter((m) => !existing.has(m.user_id));
}

// UI hint mirroring the server's is_last_owner guard: true when `userId` is
// the sole owner, so demote/remove controls can disable pre-emptively.
export function isLastOwner(ownerIds: string[], userId: string): boolean {
	return ownerIds.length === 1 && ownerIds[0] === userId;
}
