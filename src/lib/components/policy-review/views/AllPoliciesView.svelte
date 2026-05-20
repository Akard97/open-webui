<script lang="ts">
	// All Policies — workspace library view.
	// Port of all-policies.jsx from the PRP-2 design handoff.

	import Icon from '../ui/Icon.svelte';
	import {
		POLICIES,
		STATUS_DIST,
		STATUS_META,
		FN_META,
		FN_DIST,
		TOTAL_COUNT,
		TODAY
	} from '../lib/mocks';
	import type { LibraryPolicy, PolicyStatus } from '../lib/types';
	import { view, stage } from '../lib/store';

	type SortKey = 'updated' | 'next' | 'score' | 'title' | 'code';

	let status = $state<string>('all');
	let search = $state<string>('');
	let fnFilter = $state<string>('all');
	let sort = $state<SortKey>('updated');
	let listMode = $state<'list' | 'grouped'>('list');

	const initials = (name: string) =>
		name.split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase();

	const fmtUpdated = (d: number | null) => {
		if (d == null) return '—';
		if (d === 0) return 'today';
		if (d === 1) return 'yesterday';
		if (d < 7) return `${d}d ago`;
		if (d < 30) return `${Math.round(d / 7)}w ago`;
		if (d < 365) return `${Math.round(d / 30)}mo ago`;
		return `${(d / 365).toFixed(1)}y ago`;
	};

	const daysUntil = (dateStr: string): number | null => {
		if (!dateStr || dateStr === '—') return null;
		const t = new Date(dateStr);
		if (isNaN(t.getTime())) return null;
		return Math.round((t.getTime() - TODAY.getTime()) / (1000 * 60 * 60 * 24));
	};

	let filtered = $derived.by<LibraryPolicy[]>(() => {
		let rows: LibraryPolicy[] = POLICIES.slice();
		if (status !== 'all') rows = rows.filter((p) => p.status === status);
		if (fnFilter !== 'all') rows = rows.filter((p) => p.fn === fnFilter);
		if (search.trim()) {
			const q = search.toLowerCase();
			rows = rows.filter(
				(p) =>
					p.title.toLowerCase().includes(q) ||
					p.code.toLowerCase().includes(q) ||
					p.owner.toLowerCase().includes(q)
			);
		}
		if (sort === 'updated') {
			rows.sort((a, b) => (a.updatedDays ?? 9999) - (b.updatedDays ?? 9999));
		} else if (sort === 'score') {
			rows.sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
		} else if (sort === 'next') {
			rows.sort((a, b) => {
				const da = daysUntil(a.nextReview);
				const db = daysUntil(b.nextReview);
				if (da == null) return 1;
				if (db == null) return -1;
				return da - db;
			});
		} else if (sort === 'code') {
			rows.sort((a, b) => a.code.localeCompare(b.code));
		} else if (sort === 'title') {
			rows.sort((a, b) => a.title.localeCompare(b.title));
		}
		// Active review always pinned first in list view.
		if (listMode === 'list') {
			rows.sort((a, b) => (b.current ? 1 : 0) - (a.current ? 1 : 0));
		}
		return rows;
	});

	let grouped = $derived.by(() => {
		const m = new Map<string, LibraryPolicy[]>();
		filtered.forEach((p) => {
			if (!m.has(p.fn)) m.set(p.fn, []);
			m.get(p.fn)!.push(p);
		});
		return Array.from(m.entries()).map(([fn, rows]) => ({
			fn,
			rows,
			meta: FN_DIST.find((f) => f.id === fn) ?? { count: rows.length, avg: null as number | null }
		}));
	});

	let activeStatusLabel = $derived(
		status === 'all'
			? 'All policies'
			: (STATUS_DIST.find((s) => s.id === status)?.label ?? 'Filtered')
	);

	function openPolicy(p: LibraryPolicy) {
		// Per app.jsx: clicking the active in-flight policy jumps straight to
		// the review screen. Other rows would open detail (stubbed for now).
		if (p.current) {
			view.set('new-review');
			stage.set('review');
		}
	}

	function scoreTone(score: number): 'ok' | 'warn' | 'bad' {
		return score >= 85 ? 'ok' : score >= 70 ? 'warn' : 'bad';
	}

	function nextReviewTone(d: number | null): { tone: string; rel: string } {
		if (d == null) return { tone: 'muted', rel: '—' };
		if (d < 0) return { tone: 'bad', rel: `${Math.abs(d)}d overdue` };
		if (d < 30) return { tone: 'warn', rel: `in ${d}d` };
		if (d < 90) return { tone: 'warn', rel: `in ${Math.round(d / 30)}mo` };
		if (d < 365) return { tone: 'default', rel: `in ${Math.round(d / 30)}mo` };
		return { tone: 'default', rel: `in ${(d / 365).toFixed(1)}y` };
	}

	function clearFilters() {
		status = 'all';
		fnFilter = 'all';
		search = '';
	}
</script>

<div class="apx-wrap">
	<!-- Header -->
	<header class="apx-header">
		<div class="apx-hd-left">
			<div class="apx-eyebrow">Workspace · Osool Policy Library</div>
			<h1>All policies</h1>
			<div class="apx-hd-stats">
				<div class="apx-stat"><span class="n">142</span><span class="l">policies</span></div>
				<div class="apx-stat"><span class="n">10</span><span class="l">functions</span></div>
				<div class="apx-stat">
					<span class="n apx-stat-ok">89.4</span><span class="l">avg compliance</span>
				</div>
				<div class="apx-stat">
					<span class="n apx-stat-warn">16</span><span class="l">need attention</span>
				</div>
			</div>
		</div>
		<div class="apx-hd-right">
			<div class="apx-sync">
				<span class="apx-sync-dot"></span>
				<div>
					<div class="apx-sync-l">Synced 14 min ago</div>
					<div class="apx-sync-s">3 sources · Etimad, SharePoint, Drive</div>
				</div>
			</div>
			<div class="apx-hd-actions">
				<button class="btn btn-sm btn-ghost" type="button">
					<Icon name="upload" size={12} /> Import
				</button>
				<button class="btn btn-sm btn-ghost" type="button">
					<Icon name="download" size={12} /> Export
				</button>
				<button
					class="btn btn-sm btn-primary"
					onclick={() => {
						view.set('new-review');
						stage.set('upload');
					}}
					type="button"
				>
					<Icon name="plus" size={12} /> New review
				</button>
			</div>
		</div>
	</header>

	<!-- Status distribution strip -->
	<div class="apx-dist">
		<div class="apx-dist-head">
			<span class="apx-dist-eyebrow">Library status</span>
			<span class="apx-dist-meta"><b>{TOTAL_COUNT}</b> total policies · 16 active alerts</span>
		</div>
		<div class="apx-dist-bar">
			{#each STATUS_DIST as s (s.id)}
				{@const pct = (s.count / TOTAL_COUNT) * 100}
				<button
					class="apx-dist-seg apx-tone-{s.tone}"
					class:active={status === s.id}
					style="flex: {pct} 1 0"
					onclick={() => (status = status === s.id ? 'all' : s.id)}
					title={`${s.label} — ${s.count}`}
					type="button"
					aria-label={s.label}
				></button>
			{/each}
		</div>
		<div class="apx-dist-legend">
			<button
				class="apx-leg"
				class:active={status === 'all'}
				onclick={() => (status = 'all')}
				type="button"
			>
				<span class="apx-leg-sw apx-leg-all"></span>
				<span class="apx-leg-lbl">All</span>
				<span class="apx-leg-n">{TOTAL_COUNT}</span>
			</button>
			{#each STATUS_DIST as s (s.id)}
				<button
					class="apx-leg apx-tone-{s.tone}"
					class:active={status === s.id}
					onclick={() => (status = status === s.id ? 'all' : s.id)}
					type="button"
				>
					<span class="apx-leg-sw apx-tone-{s.tone}"></span>
					<span class="apx-leg-lbl">{s.label}</span>
					<span class="apx-leg-n">{s.count}</span>
				</button>
			{/each}
		</div>
	</div>

	<!-- Toolbar -->
	<div class="apx-toolbar">
		<div class="apx-search">
			<Icon name="search" size={14} />
			<input
				placeholder="Search policies, codes, or owners…"
				bind:value={search}
			/>
			{#if search}
				<button
					class="apx-search-clear"
					onclick={() => (search = '')}
					aria-label="Clear"
					type="button"
				>
					<Icon name="x" size={12} />
				</button>
			{/if}
			<span class="apx-kbd">⌘K</span>
		</div>
		<div class="apx-select">
			<Icon name="filter" size={11} />
			<span class="lbl">Function</span>
			<select bind:value={fnFilter}>
				<option value="all">All</option>
				{#each Object.entries(FN_META) as [k, v] (k)}
					<option value={k}>{v.name}</option>
				{/each}
			</select>
			<Icon name="chevD" size={11} />
		</div>
		<div class="apx-select">
			<span class="lbl">Sort</span>
			<select bind:value={sort}>
				<option value="updated">Recently updated</option>
				<option value="next">Next review</option>
				<option value="score">Compliance score</option>
				<option value="title">Title (A→Z)</option>
				<option value="code">Document code</option>
			</select>
			<Icon name="chevD" size={11} />
		</div>
		<div class="apx-spacer"></div>
		<div class="apx-vt">
			<button
				class="apx-vt-btn"
				class:active={listMode === 'list'}
				onclick={() => (listMode = 'list')}
				title="List"
				type="button"
			>
				<Icon name="sidebar" size={12} /> List
			</button>
			<button
				class="apx-vt-btn"
				class:active={listMode === 'grouped'}
				onclick={() => (listMode = 'grouped')}
				title="Grouped by function"
				type="button"
			>
				<Icon name="folder" size={12} /> By function
			</button>
		</div>
	</div>

	<!-- Result meta -->
	<div class="apx-result-meta">
		<span>
			Showing <b>{filtered.length}</b> of <b>{TOTAL_COUNT}</b>
			{#if status !== 'all'} · <em>{activeStatusLabel}</em>{/if}
			{#if fnFilter !== 'all'} · <em>{FN_META[fnFilter].name}</em>{/if}
		</span>
		{#if status !== 'all' || fnFilter !== 'all' || search}
			<button class="apx-clear-link" onclick={clearFilters} type="button">Clear filters</button>
		{/if}
	</div>

	<!-- Empty state -->
	{#if filtered.length === 0}
		<div class="apx-empty">
			<Icon name="search" size={20} />
			<h4>No policies match these filters.</h4>
			<p>Try a different search term or clear filters.</p>
		</div>
	{/if}

	<!-- List view -->
	{#if listMode === 'list' && filtered.length > 0}
		<div class="apx-list">
			<div class="apx-thead">
				<span></span>
				<div class="apx-c-policy">Policy</div>
				<div class="apx-c-score">Compliance</div>
				<div class="apx-c-status">Status</div>
				<div class="apx-c-next">Next review</div>
			</div>
			{#each filtered as p (p.code)}
				{@const meta = STATUS_META[p.status as PolicyStatus]}
				{@const d = daysUntil(p.nextReview)}
				{@const next = nextReviewTone(d)}
				<button
					class="apx-row"
					class:current={p.current}
					onclick={() => openPolicy(p)}
					type="button"
				>
					<span class="apx-rail fn-{p.fn}" aria-hidden="true"></span>
					<div class="apx-c-policy">
						<div class="apx-title-row">
							<span class="apx-title">{p.title}</span>
							{#if p.current}<span class="apx-now-tag">Active review</span>{/if}
							<span class="apx-ver">v{p.version}</span>
						</div>
						<div class="apx-meta-row">
							<span class="apx-fn-tag fn-{p.fn}">{FN_META[p.fn].name}</span>
							<span class="apx-code">{p.code}</span>
							<span class="apx-dot-sep">·</span>
							<span class="apx-owner-mini">
								<span class="apx-own-avatar">{initials(p.owner)}</span>{p.owner}
							</span>
							<span class="apx-dot-sep">·</span>
							<span>{p.pages}p</span>
							<span class="apx-dot-sep">·</span>
							<span>Updated {fmtUpdated(p.updatedDays)}</span>
						</div>
					</div>
					<div class="apx-c-score">
						{#if p.score == null}
							<span class="apx-score-empty">—</span>
						{:else}
							{@const tone = scoreTone(p.score)}
							<div class="apx-score">
								<span class="apx-score-num apx-score-{tone}">{p.score}</span>
								<div class="apx-score-bar apx-score-{tone}">
									<div class="fill" style="width: {p.score}%"></div>
								</div>
							</div>
						{/if}
					</div>
					<div class="apx-c-status">
						<span class="apx-status-chip apx-tone-{meta.tone}">
							<span class="apx-dot apx-dot-{meta.tone}" aria-label={p.status}></span>
							{meta.label}
						</span>
					</div>
					<div class="apx-c-next">
						{#if !p.nextReview || p.nextReview === '—'}
							<div class="apx-next">
								<span class="rel muted">Not scheduled</span>
								<span class="abs">—</span>
							</div>
						{:else}
							<div class="apx-next">
								<span class="rel {next.tone}">{next.rel}</span>
								<span class="abs">{p.nextReview}</span>
							</div>
						{/if}
					</div>
				</button>
			{/each}
		</div>
	{/if}

	<!-- Grouped view -->
	{#if listMode === 'grouped' && filtered.length > 0}
		<div class="apx-grouped">
			{#each grouped as g (g.fn)}
				<section class="apx-group">
					<header class="apx-group-head">
						<div class="apx-gh-left">
							<span class="apx-fn-marker fn-{g.fn}"></span>
							<h3>{FN_META[g.fn].name}</h3>
							<span class="apx-gh-count">
								{g.rows.length} <span class="muted">/ {g.meta.count} in library</span>
							</span>
						</div>
						<div class="apx-gh-right">
							{#if g.meta.avg != null}
								<div class="apx-gh-stat">
									<span class="l">Avg compliance</span>
									<span class="v">{g.meta.avg}</span>
								</div>
							{/if}
							<button class="btn btn-sm btn-ghost" type="button">
								View all <Icon name="arrowR" size={11} />
							</button>
						</div>
					</header>
					<div class="apx-group-list">
						{#each g.rows as p (p.code)}
							{@const meta = STATUS_META[p.status as PolicyStatus]}
							{@const d = daysUntil(p.nextReview)}
							{@const next = nextReviewTone(d)}
							<button
								class="apx-row"
								class:current={p.current}
								onclick={() => openPolicy(p)}
								type="button"
							>
								<span class="apx-rail fn-{p.fn}" aria-hidden="true"></span>
								<div class="apx-c-policy">
									<div class="apx-title-row">
										<span class="apx-title">{p.title}</span>
										{#if p.current}<span class="apx-now-tag">Active review</span>{/if}
										<span class="apx-ver">v{p.version}</span>
									</div>
									<div class="apx-meta-row">
										<span class="apx-fn-tag fn-{p.fn}">{FN_META[p.fn].name}</span>
										<span class="apx-code">{p.code}</span>
										<span class="apx-dot-sep">·</span>
										<span class="apx-owner-mini">
											<span class="apx-own-avatar">{initials(p.owner)}</span>{p.owner}
										</span>
										<span class="apx-dot-sep">·</span>
										<span>{p.pages}p</span>
										<span class="apx-dot-sep">·</span>
										<span>Updated {fmtUpdated(p.updatedDays)}</span>
									</div>
								</div>
								<div class="apx-c-score">
									{#if p.score == null}
										<span class="apx-score-empty">—</span>
									{:else}
										{@const tone = scoreTone(p.score)}
										<div class="apx-score">
											<span class="apx-score-num apx-score-{tone}">{p.score}</span>
											<div class="apx-score-bar apx-score-{tone}">
												<div class="fill" style="width: {p.score}%"></div>
											</div>
										</div>
									{/if}
								</div>
								<div class="apx-c-status">
									<span class="apx-status-chip apx-tone-{meta.tone}">
										<span class="apx-dot apx-dot-{meta.tone}" aria-label={p.status}></span>
										{meta.label}
									</span>
								</div>
								<div class="apx-c-next">
									{#if !p.nextReview || p.nextReview === '—'}
										<div class="apx-next">
											<span class="rel muted">Not scheduled</span>
											<span class="abs">—</span>
										</div>
									{:else}
										<div class="apx-next">
											<span class="rel {next.tone}">{next.rel}</span>
											<span class="abs">{p.nextReview}</span>
										</div>
									{/if}
								</div>
							</button>
						{/each}
					</div>
				</section>
			{/each}
		</div>
	{/if}

	<!-- Footer pagination -->
	{#if filtered.length > 0}
		<div class="apx-foot">
			<div class="apx-foot-meta">Page <b>1</b> of <b>3</b> · 50 rows per page</div>
			<div class="apx-pages">
				<button class="btn btn-sm btn-ghost" disabled type="button">
					<Icon name="chevL" size={11} /> Prev
				</button>
				<button class="apx-page active" type="button">1</button>
				<button class="apx-page" type="button">2</button>
				<button class="apx-page" type="button">3</button>
				<button class="btn btn-sm btn-ghost" type="button">
					Next <Icon name="chevR" size={11} />
				</button>
			</div>
		</div>
	{/if}
</div>

<style>
	/* The design's CSS uses div + onClick rows; we use buttons for accessibility.
	   Strip the default button chrome so the .apx-row CSS still owns the look. */
	button.apx-row {
		background: none;
		border: 0;
		text-align: left;
		width: 100%;
		font: inherit;
		color: inherit;
		padding: 0;
	}
</style>
