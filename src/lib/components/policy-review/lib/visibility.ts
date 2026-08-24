/**
 * Single source of truth for who can see the Policy Review tool.
 *
 * Visible when the admin has switched the tool on globally
 * (config.features.enable_policy_review), and always for admins and
 * users with the policy_checker permission — the people building and
 * piloting the tool while it is hidden from everyone else.
 *
 * Used by the rail (railItems.ts) and the route guard
 * (routes/(app)/policy-review/+layout.svelte) so they cannot disagree.
 */
export function canSeePolicyReview({ user, config }: { user: any; config: any }): boolean {
	return (
		(config?.features?.enable_policy_review ?? false) ||
		user?.role === 'admin' ||
		!!user?.permissions?.features?.policy_checker
	);
}
