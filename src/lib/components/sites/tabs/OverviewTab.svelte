<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import dayjs from 'dayjs';
	import relativeTime from 'dayjs/plugin/relativeTime';
	import { copyToClipboard } from '$lib/utils';
	import { getSiteAnalytics } from '$lib/apis/sites';
	import { siteAccessLevel } from '../lib/access';
	import { totalSize, formatSize } from '../lib/form';
	import type { SeriesPoint } from '../lib/analytics';
	import InsightsCard from '../InsightsCard.svelte';
	import TopPagesCard from '../TopPagesCard.svelte';
	import ViewersCard from '../ViewersCard.svelte';

	dayjs.extend(relativeTime);

	const i18n = getContext('i18n');

	let { site, onGoTab = (_t: string) => {} }: { site: any; onGoTab?: (t: string) => void } =
		$props();

	const url = $derived(`${window.location.origin}/sites/${site.slug}/`);
	const level = $derived(siteAccessLevel(site));

	const visLabel = $derived(
		{
			public: $i18n.t('Public'),
			internal: $i18n.t('Everyone'),
			specific: $i18n.t('Specific'),
			private: $i18n.t('Private')
		}[level]
	);
	const visSub = $derived(
		{
			public: $i18n.t('No login needed'),
			internal: $i18n.t('Signed-in viewers'),
			specific: $i18n.t('Signed-in viewers'),
			private: $i18n.t('Only you')
		}[level]
	);

	// Stable literal ids, never the translated label: two locales rendering
	// the same string for two different rows would make Svelte throw
	// `each_key_duplicate` at runtime.
	const details = $derived([
		{ id: 'visibility', label: $i18n.t('Visibility'), value: `${visLabel} · ${visSub}` },
		{ id: 'entry', label: $i18n.t('Entry file'), value: `${site.entry_file}` },
		{
			id: 'files',
			label: $i18n.t('Files'),
			value: `${(site.files ?? []).length} · ${formatSize(totalSize(site.files ?? []))}`
		},
		{ id: 'owner', label: $i18n.t('Owner'), value: `${site.user_name ?? $i18n.t('You')}` },
		{
			id: 'updated',
			label: $i18n.t('Updated'),
			value: `${dayjs(site.updated_at).fromNow()} · ${$i18n.t('created')} ${dayjs(site.created_at).format('MMM D, YYYY')}`
		}
	]);

	const copy = async () => {
		await copyToClipboard(url);
		toast.success($i18n.t('Link copied'));
	};

	// --- analytics ------------------------------------------------------
	// This tab owns the fetch so that both InsightsCard and TopPagesCard can
	// render from one load and the tab keeps control of where they sit.

	// Track the id, not the whole `site` object: SitesPage recomputes
	// `selected` via `sites.find(...)` on every list refresh (e.g. after a
	// settings save), which produces a new object with the same id. A
	// $derived primitive doesn't notify subscribers when its value is
	// unchanged, so keying the load effect off this instead of `site` avoids
	// a spurious reload — and the skeleton flash that comes with it — on
	// every save.
	const siteId = $derived(site.id);

	let days = $state(30);
	let loading = $state(true);
	let failed = $state(false);
	let totals = $state({ views: 0, unique_visitors: 0, owner_views: 0 });
	let series = $state<SeriesPoint[]>([]);
	let topPages = $state<{ path: string; views: number }[]>([]);
	let viewers = $state<{
		people: {
			user_id: string;
			name: string;
			profile_image_url: string | null;
			views: number;
			last_viewed_at: number;
		}[];
		anonymous_views: number;
		more: number;
	}>({ people: [], anonymous_views: 0, more: 0 });
	// Sticky across reloads: only a resolved response updates it, so a
	// loading/failed window in between never yanks the "Yours" stat in or
	// out. Reset explicitly on a site switch (see the effect below) so it
	// doesn't stay sticky across sites, only within one.
	let ownerVisible = $state(false);

	// Request-generation counter shared by every trigger that re-runs the
	// $effect below (range AND site — see the effect for why a site change
	// re-runs it too). A response is only applied if no newer request — for
	// either a different range or a different site — has started since, so a
	// slow stale response can never paint another range's, or another site's,
	// numbers under the current header. Deliberately a plain `let`, not
	// $state: it is read and written inside the effect's tracked window, and
	// making it reactive would make the effect retrigger itself.
	let loadSeq = 0;

	// One definition of "the current range's numbers are not known yet",
	// reused by the KPI numerals (passed to InsightsCard) and by the Top
	// pages gate below.
	const dataUnknown = $derived(loading || failed);
	// Keep the card mounted while loading so the two-column row doesn't
	// collapse and reflow on every range switch; it shows a skeleton, never
	// the previous site's paths.
	const showTopPages = $derived(loading || (!dataUnknown && topPages.length > 0));

	const load = async (id: string, range: number) => {
		const seq = ++loadSeq;
		loading = true;
		failed = false;
		try {
			const res = await getSiteAnalytics(localStorage.token, id, range);
			if (seq !== loadSeq) return;
			totals = res.totals;
			series = res.series;
			topPages = res.top_pages;
			viewers = res.viewers ?? { people: [], anonymous_views: 0, more: 0 };
			ownerVisible = res.totals.owner_views > 0;
		} catch (err) {
			if (seq !== loadSeq) return;
			// Analytics is two cards, not the whole tab — surface it inline and
			// let the rest of Overview render normally.
			console.error(err);
			failed = true;
			// Never leave a previous site's (or range's) roster in state: with
			// `failed` true, ViewersCard renders the failure message off this
			// prop, not off `viewers.people`, but a stale non-empty roster
			// would otherwise still sit in state ready to leak the moment
			// `failed` is misread as ok.
			viewers = { people: [], anonymous_views: 0, more: 0 };
		}
		// Reached only by the newest request: both paths above return early
		// when a newer one has started, so this write is gated too.
		loading = false;
	};

	// Plain (non-reactive) variable: only used to detect, from inside the
	// effect, whether this run was triggered by a site change vs. a range
	// change — it must not itself be a dependency.
	let prevSiteId: string | undefined;

	$effect(() => {
		// Depends on `siteId` (derived from site.id) and `days`, not the whole
		// `site` object — see the comment on `siteId` above for why. A range
		// change on the same site still re-runs this exactly like before,
		// since `days` is read here too.
		if (siteId !== prevSiteId) {
			// Site actually changed (not just a range click): drop the sticky
			// "Yours" tile from the previous site immediately instead of
			// carrying it into the new site's loading/failed window, where it
			// would otherwise linger until (or unless) a response resolves.
			ownerVisible = false;
			prevSiteId = siteId;
		}
		load(siteId, days);
	});
</script>

<div class="st-pane flex flex-col gap-4">
	<div class="flex flex-wrap items-center gap-3 rounded-xl bg-gray-50 px-4 py-3.5 dark:bg-gray-850">
		<span class="min-w-0 flex-1 truncate text-sm text-gray-600 dark:text-gray-300">{url}</span>
		<div class="flex gap-2">
			<button type="button" class="st-btn" onclick={copy}>{$i18n.t('Copy link')}</button>
			<a
				class="st-btn st-btn-primary inline-flex items-center"
				href={url}
				target="_blank"
				rel="noopener">{$i18n.t('Open site')} ↗</a
			>
		</div>
	</div>

	<InsightsCard
		{days}
		{loading}
		{failed}
		{dataUnknown}
		{totals}
		{series}
		{ownerVisible}
		onRangeChange={(d) => (days = d)}
	/>

	<div class="grid gap-4 lg:grid-cols-2">
		<ViewersCard {loading} {failed} {viewers} />
		{#if showTopPages}
			<TopPagesCard {loading} {topPages} />
		{/if}
	</div>

	<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-3.5">
		<h4 class="mb-2 text-xs font-medium text-gray-400 dark:text-gray-500">
			{$i18n.t('Details')}
		</h4>
		{#each details as row, i (row.id)}
			<div
				class="flex justify-between gap-3 py-1.5 text-[13px] {i < details.length - 1
					? 'border-b border-[var(--st-hairline)]'
					: ''}"
			>
				<span class="text-[var(--st-muted)]">{row.label}</span>
				<span class="truncate text-right" title={row.value}>{row.value}</span>
			</div>
		{/each}
	</div>

	<div
		class="flex flex-wrap items-center gap-1.5"
		role="group"
		aria-label={$i18n.t('Quick actions')}
	>
		{#each [[$i18n.t('Replace files'), 'files'], [$i18n.t('Change who can view'), 'settings'], [$i18n.t('Restore an older version'), 'versions']] as [label, target] (target)}
			<button
				type="button"
				class="st-press rounded-[7px] px-2.5 py-1.5 text-xs text-[var(--st-muted)] hover:bg-[var(--st-hover)] hover:text-[var(--st-ink)]"
				onclick={() => onGoTab(target as string)}>{label} →</button
			>
		{/each}
	</div>
</div>
