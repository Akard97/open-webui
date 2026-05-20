<script lang="ts">
	// Review stage — themed checklist + side rail summary.
	// Port of review.jsx from the PRP-2 design handoff.

	import Icon from '../ui/Icon.svelte';
	import VerdictBadge from '../ui/VerdictBadge.svelte';
	import StatusCircle from '../ui/StatusCircle.svelte';
	import OEBanner from './OEBanner.svelte';
	import { computeScores } from '../lib/scoring';
	import { THEMES, POLICY_META } from '../lib/mocks';
	import type { Section, ChecklistItem } from '../lib/types';
	import {
		sections,
		picked,
		drawerOpen,
		oeState,
		oeModalOpen
	} from '../lib/store';

	type Filter = 'all' | 'issues' | 'human' | 'compliant';

	let openMap = $state<Record<string, boolean>>({});
	let filter = $state<Filter>('all');

	function setOpen(id: string, v: boolean) {
		openMap = { ...openMap, [id]: v };
	}

	let scoreResult = $derived(computeScores($sections, THEMES));

	let counts = $derived.by(() => {
		const c: Record<string, number> = {};
		$sections.forEach((sec) =>
			sec.items.forEach((it) => {
				c[it.result] = (c[it.result] || 0) + 1;
			})
		);
		return c;
	});

	let totalItems = $derived(
		$sections.reduce((a, sec) => a + sec.items.length, 0)
	);

	// Top gaps: non-compliant items, T1/T2 first.
	let topGaps = $derived.by(() => {
		const gaps: { ref: string; title: string; theme: string; comment?: string }[] = [];
		$sections.forEach((sec) =>
			sec.items.forEach((it) => {
				if (it.result === 'non-compliant') {
					gaps.push({
						ref: `${sec.id}.${it.n}`,
						title: it.text.replace(' [H]', ''),
						theme: sec.theme,
						comment: it.comment
					});
				}
			})
		);
		const rank: Record<string, number> = { T1: 0, T2: 1, T3: 2, T4: 3, T5: 4, T6: 5 };
		gaps.sort((a, b) => (rank[a.theme] ?? 9) - (rank[b.theme] ?? 9));
		return gaps.slice(0, 5);
	});

	const strengths = [
		'Comprehensive RACI with explicit segregation of duties (§4)',
		'Strong escalation and approval flow with named final authority',
		'Complete dependency mapping in References (§11)'
	];

	let byTheme = $derived.by(() => {
		const out: Record<string, Section[]> = {};
		THEMES.forEach((t) => (out[t.id] = []));
		$sections.forEach((s) => out[s.theme]?.push(s));
		return out;
	});

	function itemMatchesFilter(it: ChecklistItem): boolean {
		if (filter === 'all') return true;
		if (filter === 'issues') return it.result === 'non-compliant';
		if (filter === 'human') return it.result === 'human';
		if (filter === 'compliant') return it.result === 'compliant';
		return true;
	}

	function pickItem(sec: Section, it: ChecklistItem) {
		picked.set({ sectionId: sec.id, n: it.n });
		drawerOpen.set(true);
	}

	function selectedKey(sec: Section, it: ChecklistItem): boolean {
		const p = $picked;
		return !!p && p.sectionId === sec.id && p.n === it.n;
	}

	function sectionCounts(sec: Section): Record<string, number> {
		return sec.items.reduce(
			(a, it) => {
				a[it.result] = (a[it.result] || 0) + 1;
				return a;
			},
			{} as Record<string, number>
		);
	}

	function sectionVisibleItems(sec: Section): ChecklistItem[] {
		return sec.items.filter(itemMatchesFilter);
	}

	function themeHasVisible(themeId: string): Section[] {
		return (byTheme[themeId] ?? []).filter((sec) =>
			sec.items.some(itemMatchesFilter)
		);
	}

	function collapseAll() {
		const m: Record<string, boolean> = {};
		$sections.forEach((s) => (m[s.id] = false));
		openMap = m;
	}
	function expandAll() {
		openMap = {};
	}

	function openOE() {
		oeModalOpen.set(true);
	}
</script>

<div class="review">
	<div class="review-main">
		<!-- OE Banner -->
		{#if $oeState.status !== 'idle'}
			<OEBanner />
		{/if}

		<!-- Policy header -->
		<div class="policy-header">
			<div style="min-width:0; flex:1">
				<h1 class="policy-title">{POLICY_META.name}</h1>
				<div class="policy-tags">
					<span>{POLICY_META.code}</span><span class="dot">·</span>
					<span>{POLICY_META.version}</span><span class="dot">·</span>
					<span>{POLICY_META.pages} pages</span><span class="dot">·</span>
					<span>Reviewed {POLICY_META.reviewDate}</span><span class="dot">·</span>
					<span>Reviewer: {POLICY_META.reviewer}</span>
				</div>
			</div>
			<VerdictBadge verdict={scoreResult.verdict} />
		</div>

		<!-- Filters -->
		<div class="review-toolbar">
			<button
				class="chip"
				class:active={filter === 'all'}
				onclick={() => (filter = 'all')}
				type="button"
			>
				All <span class="count">{totalItems}</span>
			</button>
			<button
				class="chip"
				class:active={filter === 'issues'}
				onclick={() => (filter = 'issues')}
				type="button"
			>
				<Icon name="alert" size={12} /> Non-Compliant
				<span class="count">{counts['non-compliant'] || 0}</span>
			</button>
			<button
				class="chip"
				class:active={filter === 'human'}
				onclick={() => (filter = 'human')}
				type="button"
			>
				<Icon name="user" size={12} /> Needs Human
				<span class="count">{counts.human || 0}</span>
			</button>
			<button
				class="chip"
				class:active={filter === 'compliant'}
				onclick={() => (filter = 'compliant')}
				type="button"
			>
				<Icon name="check" size={12} stroke={3} /> Compliant
				<span class="count">{counts.compliant || 0}</span>
			</button>
			<div style="flex:1"></div>
			<button class="btn btn-sm btn-ghost" onclick={expandAll} type="button">
				<Icon name="chevD" size={12} /> Expand all
			</button>
			<button class="btn btn-sm btn-ghost" onclick={collapseAll} type="button">
				<Icon name="chevR" size={12} /> Collapse
			</button>
		</div>

		<!-- Themes -->
		{#each THEMES as theme (theme.id)}
			{@const visibleSecs = themeHasVisible(theme.id)}
			{#if visibleSecs.length > 0}
				{@const themeData = scoreResult.themeRows.find((t) => t.id === theme.id)}
				{#if themeData}
					<div class="theme">
						<div class="theme-head">
							<h2>
								<span class="theme-id {theme.id.toLowerCase()}">{theme.id}</span>
								{theme.name}
								{#if theme.gate}
									<span class="gate-tag">MANDATORY GATE</span>
								{/if}
							</h2>
							<div class="theme-stats">
								<span><b>{themeData.pct}%</b> score</span>
								<span>{themeData.yes}/{themeData.total} compliant</span>
								{#if themeData.human}
									<span>{themeData.human} human</span>
								{/if}
								<span><b>{theme.weight}%</b> weight</span>
							</div>
						</div>

						{#each visibleSecs as sec (sec.id)}
							{@const isOpen = openMap[sec.id] !== false}
							{@const items = sectionVisibleItems(sec)}
							{@const c = sectionCounts(sec)}
							{#if items.length > 0 || filter === 'all'}
								<div class="section" class:open={isOpen}>
									<button
										class="sec-head"
										onclick={() => setOpen(sec.id, !isOpen)}
										type="button"
									>
										<div class="left">
											<span class="chev"><Icon name="chevR" size={14} /></span>
											<div class="titleblock">
												<div class="prp">{sec.id} · {sec.codes}</div>
												<h3>{sec.title}</h3>
												<div class="intent">{sec.intent}</div>
											</div>
										</div>
										<div class="right">
											{#if c.compliant}
												<span class="minibadge ok">
													<span class="dot"></span>{c.compliant}
												</span>
											{/if}
											{#if c['non-compliant']}
												<span class="minibadge bad">
													<span class="dot"></span>{c['non-compliant']}
												</span>
											{/if}
											{#if c.human}
												<span class="minibadge warn">
													<span class="dot"></span>{c.human}
												</span>
											{/if}
										</div>
									</button>

									{#if isOpen}
										<div class="sec-body">
											{#each items as it (it.n)}
												<button
													class="item-row"
													class:selected={selectedKey(sec, it)}
													onclick={() => pickItem(sec, it)}
													type="button"
												>
													<div class="item-num">{sec.id.replace('PRP', '')}.{it.n}</div>
													<div class="item-status">
														<StatusCircle result={it.result} />
													</div>
													<div class="item-text">
														{it.text.replace(' [H]', '')}
														<div class="meta">
															<span>{it.code}</span>
															{#if it.confidence != null && it.result !== 'human'}
																<span class="conf">
																	confidence {Math.round(it.confidence * 100)}%
																</span>
															{/if}
															{#if it.reviewed}
																<span style="color:var(--primary)">· deep-reviewed</span>
															{/if}
															{#if it.edited}
																<span style="color:var(--ink-500)">· edited</span>
															{/if}
														</div>
													</div>
													<div class="item-arrow"><Icon name="chevR" size={14} /></div>
												</button>
											{/each}
										</div>
									{/if}
								</div>
							{/if}
						{/each}
					</div>
				{/if}
			{/if}
		{/each}
	</div>

	<!-- Side rail -->
	<aside class="review-side">
		<div class="side-card">
			<h4>Decision</h4>
			<div class="score-block">
				<div class="num">{scoreResult.overall}<span class="pct">%</span></div>
				<div class="lbl">weighted score</div>
				<div style="margin-top:14px">
					<VerdictBadge verdict={scoreResult.verdict} />
				</div>
			</div>
			<div class="decision-summary">
				<div class="row">
					<span class="l">Mandatory gates</span>
					<span class="r" style="color: {scoreResult.gatesPass ? 'var(--ok)' : 'var(--bad)'}">
						{scoreResult.gatesPass ? 'Both pass' : 'Not passing'}
					</span>
				</div>
				<div class="row"><span class="l">Threshold for issue</span><span class="r">≥ 85%</span></div>
				<div class="row">
					<span class="l">Items pending human</span>
					<span class="r">{counts.human || 0}</span>
				</div>
			</div>
			<div style="margin-top:14px; display:grid; gap:8px">
				<button
					class="btn btn-primary"
					onclick={openOE}
					disabled={scoreResult.humanItemsRemain || $oeState.status === 'pending'}
					style="justify-content:center"
					type="button"
				>
					<Icon name="send" size={13} />
					{$oeState.status === 'pending' ? 'Submitted to OE' : 'Send to OE for Approval'}
				</button>
				{#if scoreResult.humanItemsRemain}
					<div style="font-size:11.5px; color:var(--ink-500); text-align:center">
						Resolve {counts.human} human-review item{counts.human === 1 ? '' : 's'} before submission
					</div>
				{/if}
			</div>
		</div>

		<div class="side-card">
			<h4>Score by Theme</h4>
			<div style="display:grid; gap:12px">
				{#each scoreResult.themeRows as t (t.id)}
					{@const isFail = t.gate && t.pct < (t.threshold || 85) && t.total > 0}
					{@const isWarn = t.pct < 70 && !isFail && t.total > 0}
					{@const cls = isFail ? 'fail' : isWarn ? 'warn' : ''}
					<div>
						<div class="theme-score-row">
							<span class="id">{t.id}</span>
							<span class="name">
								<span class="nm">{t.name}</span>
								{#if t.gate}<span class="gate-mini">GATE</span>{/if}
							</span>
							<span class="val {cls}">{t.pct}%</span>
						</div>
						<div class="theme-score-bar">
							<div class="fill {cls}" style="width: {t.pct}%"></div>
						</div>
					</div>
				{/each}
			</div>
		</div>

		<div class="side-card">
			<h4>Top Strengths</h4>
			<div class="gap-list">
				{#each strengths as s, i (i)}
					<div class="gap-item strength">
						<span class="n">+</span>
						<span>{s}</span>
					</div>
				{/each}
			</div>
		</div>

		<div class="side-card">
			<h4>Critical Gaps — Must Be Resolved</h4>
			{#if topGaps.length === 0}
				<div style="font-size:12.5px; color:var(--ink-500)">No critical gaps remain.</div>
			{:else}
				<div class="gap-list">
					{#each topGaps as g, i (g.ref)}
						<div class="gap-item">
							<span class="n">{i + 1}</span>
							<div>
								<div style="color:var(--ink-900); font-weight:500; margin-bottom:2px">
									{g.title}
								</div>
								<div
									style="font-size:11.5px; color:var(--ink-400); font-family:var(--mono)"
								>
									{g.ref} · {g.theme}
								</div>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</aside>
</div>

<style>
	/* Sec-head was a div in the design; we use a button for accessibility.
	   Strip default button chrome so .sec-head CSS owns the look. */
	button.sec-head,
	button.item-row {
		background: none;
		border: 0;
		width: 100%;
		text-align: left;
		font: inherit;
		color: inherit;
		padding: 0;
	}
</style>
