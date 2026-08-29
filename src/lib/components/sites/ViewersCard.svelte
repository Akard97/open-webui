<script lang="ts">
	import { getContext } from 'svelte';
	import dayjs from 'dayjs';
	import relativeTime from 'dayjs/plugin/relativeTime';
	import { formatCount, viewerInitials } from './lib/analytics';

	dayjs.extend(relativeTime);

	const i18n = getContext('i18n');

	// Presentational: OverviewTab owns the fetch and hands the roster down.
	let {
		loading = false,
		failed = false,
		viewers = { people: [], anonymous_views: 0, more: 0 }
	}: {
		loading?: boolean;
		failed?: boolean;
		viewers?: {
			people: {
				user_id: string;
				name: string;
				profile_image_url: string | null;
				views: number;
				last_viewed_at: number;
			}[];
			anonymous_views: number;
			more: number;
		};
	} = $props();

	const locale = $derived($i18n.language);
	const isEmpty = $derived(
		!loading && viewers.people.length === 0 && viewers.anonymous_views === 0
	);
</script>

<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-3.5">
	<h4 class="mb-2 text-xs font-medium text-gray-400 dark:text-gray-500">
		{$i18n.t('Viewers')}
	</h4>
	{#if loading}
		<!-- A skeleton, never the roster still in state: those names belong to
		     the previous site (or range) and must not appear under a new header. -->
		<div class="space-y-2 py-1.5" aria-hidden="true">
			<div class="h-3 animate-pulse rounded bg-[var(--st-hover)]"></div>
			<div class="h-3 w-4/5 animate-pulse rounded bg-[var(--st-hover)]"></div>
			<div class="h-3 w-3/5 animate-pulse rounded bg-[var(--st-hover)]"></div>
		</div>
	{:else if failed}
		<div class="py-1.5 text-[13px] text-[var(--st-muted)]">{$i18n.t("Couldn't load viewers.")}</div>
	{:else if isEmpty}
		<div class="py-1.5 text-[13px] text-[var(--st-muted)]">{$i18n.t('No viewers yet')}</div>
	{:else}
		{#each viewers.people as p (p.user_id)}
			<div
				class="flex items-center gap-2.5 border-b border-[var(--st-hairline)] py-1.5 text-[13px] last:border-b-0"
			>
				{#if p.profile_image_url}
					<img class="size-6 shrink-0 rounded-full object-cover" src={p.profile_image_url} alt="" />
				{:else}
					<span
						class="flex size-6 shrink-0 items-center justify-center rounded-full bg-[var(--st-accent-soft)] text-[10px] font-semibold text-[var(--st-accent-soft-ink)]"
						aria-hidden="true">{viewerInitials(p.name)}</span
					>
				{/if}
				<span class="min-w-0 flex-1 truncate" title={p.name}>{p.name}</span>
				<span class="shrink-0 text-[11px] text-[var(--st-faint)]"
					>{dayjs(p.last_viewed_at).fromNow()}</span
				>
				<span class="w-12 shrink-0 text-right tabular-nums text-[var(--st-muted)]"
					>{formatCount(p.views, locale)}</span
				>
			</div>
		{/each}

		{#if viewers.anonymous_views > 0}
			<!-- Sorts last regardless of count: an aggregate over many people is
			     a different kind of row from a named one, and it has no single
			     last-seen time to report. -->
			<div
				class="flex items-center gap-2.5 border-b border-[var(--st-hairline)] py-1.5 text-[13px] last:border-b-0"
			>
				<span
					class="flex size-6 shrink-0 items-center justify-center rounded-full bg-[var(--st-hover)] text-[10px] text-[var(--st-faint)]"
					aria-hidden="true">·</span
				>
				<span class="min-w-0 flex-1 truncate text-[var(--st-muted)]">{$i18n.t('Anonymous')}</span>
				<span class="w-12 shrink-0 text-right tabular-nums text-[var(--st-muted)]"
					>{formatCount(viewers.anonymous_views, locale)}</span
				>
			</div>
		{/if}

		{#if viewers.more > 0}
			<div class="pt-1.5 text-[11px] text-[var(--st-faint)]">
				{$i18n.t('+{{count}} more', { count: viewers.more })}
			</div>
		{/if}
	{/if}
</div>
