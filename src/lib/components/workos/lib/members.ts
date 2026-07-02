import type { Member } from './types';

// Pure helpers for the sidebar access dialogs. The server stays the authority
// on every rule mirrored here (last-owner guard, membership checks); these
// only shape the UI (picker candidates, pre-emptively disabled controls).

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
