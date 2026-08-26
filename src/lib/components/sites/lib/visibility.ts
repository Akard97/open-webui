/**
 * Single source of truth for who can see the Site Publisher tool.
 * Admins always; otherwise the admin-granted site_publisher permission.
 * Used by the rail (railItems.ts) and the route guard
 * (routes/(app)/sites/+layout.svelte) so they cannot disagree.
 */
export function canSeeSites({ user }: { user: any }): boolean {
	return user?.role === 'admin' || !!user?.permissions?.features?.site_publisher;
}
