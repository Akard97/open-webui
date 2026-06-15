<script lang="ts">
	// Policy Library — bilingual reference library of approved policies.
	// See docs/superpowers/specs/2026-05-21-all-policies-redesign-design.md.

	import { onMount } from 'svelte';
	import { FN_META, TODAY } from '../lib/seed';
	import type { LibraryPolicy } from '../lib/types';
	import { openPolicyPopup, publishedPolicies } from '../lib/store';
	import {
		isFresh,
		filterPolicies,
		groupByFunctionDesc,
		recentlyUpdated
	} from '../lib/library';

	// Resting-state filters
	let query = $state('');
	let fn = $state<'all' | string>('all');

	// Loading state — mocks are synchronous but the real catalog will be
	// async. Simulated 250ms delay so the skeleton is exercised in dev.
	let loading = $state(true);
	onMount(() => {
		const t = setTimeout(() => (loading = false), 250);
		return () => clearTimeout(t);
	});

	// Library universe = approved policies only
	let approvedAll = $derived($publishedPolicies.filter((p) => p.status === 'approved'));

	const filtered = $derived(filterPolicies(approvedAll, { query, fn }));
	const groups = $derived(groupByFunctionDesc(filtered, FN_META));
	const recent = $derived(recentlyUpdated(approvedAll, 4, 30));

	let totalApproved = $derived(approvedAll.length);
	const totalFunctions = Object.keys(FN_META).length;
	let updatedThisMonth = $derived(approvedAll.filter((p) => (p.updatedDays ?? 9999) <= 30).length);

	const fmtUpdated = (d: number | null | undefined): string => {
		if (d == null) return '—';
		if (d === 0) return 'today';
		if (d === 1) return '1d ago';
		if (d < 7) return `${d}d ago`;
		if (d < 30) return `${Math.round(d / 7)}w ago`;
		if (d < 365) return `${Math.round(d / 30)}mo ago`;
		return `${(d / 365).toFixed(1)}y ago`;
	};

	const abs = (d: number | null | undefined): string => {
		if (d == null) return '';
		const date = new Date(TODAY.getTime() - d * 24 * 60 * 60 * 1000);
		return date.toISOString().slice(0, 10);
	};

	const fnClass = (id: string) => `pl-fn-${id.toLowerCase()}`;
	const rowClass = (id: string) => `pl-row-${id.toLowerCase()}`;
	const secClass = (id: string) => `pl-sec-${id.toLowerCase()}`;

	const fnMarkLetter = (name: string): string => name.charAt(0).toUpperCase();

	// Inline one-line descriptors per function. Static — could move to FN_META later.
	const FN_DESC: Record<string, string> = {
		RE: 'Real estate investment, valuation, leasing, and acquisition.',
		FIN: 'Investments, treasury, capital allocation, and reporting.',
		GOV: 'Board governance, conduct, conflicts of interest.',
		HR: 'People, leave, conduct, recruitment, and performance.',
		IT: 'Systems, data, security, and access.',
		RM: 'Enterprise, investment, business-continuity, and crisis risk.',
		LEG: 'Contracting, litigation, and intellectual property.',
		PROC: 'Vendor onboarding, tendering, and local content.',
		HSE: 'Workplace safety and environmental compliance.',
		OPS: 'Records, travel, and operational support.'
	};

	function chipClick(id: 'all' | string) {
		fn = fn === id ? 'all' : id;
	}

	function clearFilters() {
		query = '';
		fn = 'all';
	}

	function rowClick(p: LibraryPolicy) {
		openPolicyPopup(p);
	}
</script>

<div class="pl-wrap">
	<div class="pl-brand-line" aria-hidden="true"></div>

	<div class="pl-scroll">
		<!-- Hero -->
		<header class="pl-hero">
			<div class="pl-eyebrow">
				<span class="em">Osool Intelligence Hub</span>
				<span class="d" aria-hidden="true"></span>
				<span>Policy Review</span>
				<span class="d" aria-hidden="true"></span>
				<span>Library</span>
			</div>

			<div class="pl-title-block">
				<h1>Policy library</h1>
				<span class="pl-title-divider" aria-hidden="true"></span>
				<span class="pl-title-ar" lang="ar" dir="rtl">مكتبة السياسات</span>
			</div>

			<div class="pl-hero-stats">
				<div class="pl-stat lead">
					<span class="v">{totalApproved}</span>
					<span class="l">Approved</span>
				</div>
				<span class="pl-stats-sep">·</span>
				<div class="pl-stat">
					<span class="v">{totalFunctions}</span>
					<span class="l">Functions</span>
				</div>
				<span class="pl-stats-sep">·</span>
				<div class="pl-stat">
					<span class="v">{updatedThisMonth}<span class="small">/{totalApproved}</span></span>
					<span class="l">Updated this month</span>
				</div>
			</div>
		</header>

		{#if loading}
			<!-- Skeleton -->
			<div class="pl-recent" aria-hidden="true">
				<div class="pl-recent-h">
					<span style="background: var(--ink-100); width: 120px; height: 10px; border-radius: 3px;"></span>
					<span class="line"></span>
				</div>
				<div class="pl-recent-cards">
					{#each [0, 1, 2, 3] as i (i)}
						<div class="pl-rc pl-skel-card"></div>
					{/each}
				</div>
			</div>
			<div class="pl-controls">
				<div class="pl-search pl-skel-bar"></div>
			</div>
			{#each [0, 1, 2] as i (i)}
				<section class="pl-sec">
					<header class="pl-sec-h">
						<div class="pl-mark pl-skel-mark" style="border-color: var(--ink-200);"></div>
						<div class="pl-skel-title"></div>
						<div class="pl-skel-count"></div>
					</header>
					{#each [0, 1, 2] as j (j)}
						<div class="pl-skel-row"></div>
					{/each}
				</section>
			{/each}
		{:else}

		<!-- Recently updated strip -->
		<section class="pl-recent" aria-labelledby="pl-recent-h">
			<div class="pl-recent-h">
				<span id="pl-recent-h">Recently updated</span>
				<span class="line" aria-hidden="true"></span>
				<span class="sub">past 30 days</span>
			</div>
			<div class="pl-recent-cards">
				{#each recent as p (p.code)}
					<button
						class="pl-rc {fnClass(p.fn)}"
						type="button"
						onclick={() => rowClick(p)}
					>
						<span class="accent" aria-hidden="true"></span>
						<div class="fn">{FN_META[p.fn]?.name ?? p.fn}</div>
						<div class="t">{p.title}</div>
						<div class="meta">
							<span><bdi>{p.code}</bdi></span>
							<span class="when">{fmtUpdated(p.updatedDays)}</span>
						</div>
					</button>
				{/each}
			</div>
		</section>

		<!-- Search + chips -->
		<div class="pl-controls">
			<div class="pl-search">
				<input
					type="search"
					bind:value={query}
					placeholder="Search policies, codes, owners…"
					aria-label="Search the policy library"
				/>
				{#if query}
					<button
						class="pl-search-clear"
						type="button"
						onclick={() => (query = '')}
						aria-label="Clear search"
					>×</button>
				{/if}
				<span class="kbd" aria-hidden="true">⌘K</span>
			</div>

			<div class="pl-chips" role="tablist" aria-label="Filter by function">
				<button
					class="pl-chip"
					class:active={fn === 'all'}
					type="button"
					role="tab"
					aria-selected={fn === 'all'}
					onclick={() => (fn = 'all')}
				>All</button>
				{#each Object.entries(FN_META) as [id, meta] (id)}
					<button
						class="pl-chip"
						class:active={fn === id}
						type="button"
						role="tab"
						aria-selected={fn === id}
						onclick={() => chipClick(id)}
					>{meta.name}</button>
				{/each}
			</div>
		</div>

		<!-- Empty state -->
		{#if groups.length === 0}
			<div class="pl-empty">
				No policies match
				{#if query}<em>"{query}"</em>{/if}{#if fn !== 'all'} in <em>{FN_META[fn].name}</em>{/if}.
				<button class="clear" type="button" onclick={clearFilters}>Clear filters</button>
			</div>
		{/if}

		<!-- Sections -->
		{#each groups as g (g.fn)}
			<section class="pl-sec {secClass(g.fn)}">
				<header class="pl-sec-h">
					<div class="pl-mark" aria-hidden="true">{fnMarkLetter(g.name)}</div>
					<div class="pl-sec-title">
						<h3>
							{g.name}
							{#if FN_DESC[g.fn]}<span class="desc">{FN_DESC[g.fn]}</span>{/if}
						</h3>
					</div>
					<div class="pl-sec-meta">
						<span class="count">{g.policies.length}</span>
						<span class="cl">policies</span>
					</div>
				</header>

				{#each g.policies as p (p.code)}
					<button
						class="pl-row {rowClass(p.fn)}"
						class:fresh={isFresh(p.updatedDays)}
						type="button"
						onclick={() => rowClick(p)}
						aria-label="Open {p.title}"
					>
						<span class="pl-rail" aria-hidden="true"></span>
						<div class="body">
							<div class="title">{p.title}</div>
							<div class="meta">
								<span class="code"><bdi>{p.code}</bdi></span>
								<span class="sep" aria-hidden="true">·</span>
								<span>{p.owner}</span>
							</div>
						</div>
						<div class="updated">
							<span class="ago">{fmtUpdated(p.updatedDays)}</span>
							<span class="when"><bdi>{abs(p.updatedDays)}</bdi></span>
						</div>
						<span class="pl-chev" aria-hidden="true">→</span>
					</button>
				{/each}
			</section>
		{/each}
		{/if}
	</div>
</div>
