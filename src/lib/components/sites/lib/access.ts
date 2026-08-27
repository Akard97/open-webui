/**
 * Single source of truth for interpreting a site's access grants in the UI.
 * Used by SitesPage (badge) and SiteEditor (level radios) so they cannot
 * disagree.
 */
export type SiteGrant = {
	principal_type?: string;
	principal_id?: string;
	permission?: string;
};

/**
 * The "everyone with an account" wildcard is exactly user:* with read.
 * Matching on principal_id === '*' alone would misclassify a group whose id
 * happened to be '*' or a non-read wildcard grant.
 */
export const isEveryoneGrant = (g: SiteGrant | null | undefined): boolean =>
	g?.principal_type === 'user' && g?.principal_id === '*' && g?.permission === 'read';

export type SiteAccessLevel = 'public' | 'internal' | 'specific' | 'private';

export const siteAccessLevel = (
	site: { public?: boolean; access_grants?: SiteGrant[] } | null | undefined
): SiteAccessLevel => {
	if (site?.public) return 'public';
	const grants = site?.access_grants ?? [];
	if (grants.some(isEveryoneGrant)) return 'internal';
	if (grants.length > 0) return 'specific';
	return 'private';
};
