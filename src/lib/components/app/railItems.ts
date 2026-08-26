import type { ComponentType, SvelteComponent } from 'svelte';

import Home from '$lib/components/icons/Home.svelte';
import Sparkles from '$lib/components/icons/Sparkles.svelte';
import Note from '$lib/components/icons/Note.svelte';
import Cube from '$lib/components/icons/Cube.svelte';
import DocumentCheck from '$lib/components/icons/DocumentCheck.svelte';
import Clipboard from '$lib/components/icons/Clipboard.svelte';
import UserGroup from '$lib/components/icons/UserGroup.svelte';
import GlobeAlt from '$lib/components/icons/GlobeAlt.svelte';
import { canSeePolicyReview } from '$lib/components/policy-review/lib/visibility';
import { canSeeSites } from '$lib/components/sites/lib/visibility';

export type RailIconComponent = ComponentType<SvelteComponent<{ className?: string; strokeWidth?: string }>>;

export type RailVisibilityContext = {
	user: any;
	config: any;
};

export type RailItem = {
	id: string;
	/** i18n key passed to $i18n.t() at render time. */
	label: string;
	href: string;
	icon: RailIconComponent;
	/**
	 * First path segments that mark this rail item active.
	 * Use the empty string '' to match the root path `/`.
	 */
	segments: string[];
	visible: (ctx: RailVisibilityContext) => boolean;
};

/**
 * Single source of truth for the Hub's top-level navigation.
 *
 * Consumed by the desktop rail (AppSidebar.svelte) and the mobile drawer
 * (MobileRailDrawer.svelte). The future /home tool grid will read from the
 * same array so adding a new tool is a one-line change here.
 *
 * Visibility predicates mirror the patterns in
 * frontend/open-webui/src/lib/components/layout/Sidebar.svelte
 * (isMenuItemVisible) so the rail and the chat sidebar's pinned items
 * stay in sync about who can see what.
 */
export const railItems: RailItem[] = [
	{
		id: 'home',
		label: 'Home',
		href: '/home',
		icon: Home,
		segments: ['home'],
		visible: () => true
	},
	{
		id: 'chat',
		label: 'Osool AI',
		href: '/',
		icon: Sparkles,
		segments: ['', 'c', 'channels'],
		visible: () => true
	},
	{
		id: 'notes',
		label: 'Notes',
		href: '/notes',
		icon: Note,
		segments: ['notes'],
		visible: ({ user, config }) =>
			(config?.features?.enable_notes ?? false) &&
			(user?.role === 'admin' || (user?.permissions?.features?.notes ?? true))
	},
	{
		id: 'workspace',
		label: 'Workspace',
		href: '/workspace',
		icon: Cube,
		segments: ['workspace'],
		visible: ({ user }) =>
			user?.role === 'admin' ||
			!!user?.permissions?.workspace?.models ||
			!!user?.permissions?.workspace?.knowledge ||
			!!user?.permissions?.workspace?.prompts ||
			!!user?.permissions?.workspace?.tools
	},
	{
		// Policy Review tool. Hidden while in development: the
		// ENABLE_POLICY_REVIEW admin toggle (Admin Settings > General) reveals
		// it to everyone; admins and policy_checker users always see it. The
		// checker workflow inside the tool stays gated by canUseChecker
		// (see policy-review/lib/store.ts).
		id: 'policy-review',
		label: 'Policy Review',
		href: '/policy-review',
		icon: DocumentCheck,
		segments: ['policy-review'],
		visible: canSeePolicyReview
	},
	{
		// Site Publisher bonus tool. Visible to admins and users the admin
		// has granted the site_publisher permission.
		id: 'sites',
		label: 'Sites',
		href: '/sites',
		icon: GlobeAlt,
		segments: ['sites'],
		visible: ({ user }) => canSeeSites({ user })
	},
	{
		// WorkOS task-management tool. Placeholder for now — visible to everyone,
		// like Policy Review. A `features.workos` gate will be added once the tool
		// is actually built out.
		id: 'workos',
		label: 'WorkOS',
		href: '/workos',
		icon: Clipboard,
		segments: ['workos'],
		visible: ({ user }) =>
			user?.role === 'admin' || (user?.permissions?.features?.workos ?? true)
	},
	{
		id: 'admin',
		label: 'Admin Panel',
		href: '/admin',
		icon: UserGroup,
		segments: ['admin'],
		visible: ({ user }) => user?.role === 'admin'
	}
];

/**
 * Returns the rail item whose `segments` match the first segment of the
 * given pathname, or undefined if no item matches. `/` collapses to ''.
 */
export function activeRailItem(pathname: string, items: RailItem[] = railItems): RailItem | undefined {
	const segment = pathname.replace(/^\/+/, '').split('/')[0] ?? '';
	return items.find((item) => item.segments.includes(segment));
}
