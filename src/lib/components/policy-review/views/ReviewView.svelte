<script lang="ts">
	// Review stage — overview band on top, three-tier collapsible checklist below.
	import Icon from '../ui/Icon.svelte';
	import StatusCircle from '../ui/StatusCircle.svelte';
	import ReviewSummaryBand from './ReviewSummaryBand.svelte';
	import { computeScores } from '../lib/scoring';
	import { countResults, initOpenMap, itemNumber } from '../lib/reviewView';
	import type { Section, ChecklistItemDef, ItemResult } from '../lib/types';
	import { activeReview, activeVersion, picked, drawerOpen } from '../lib/store';

	type Filter = 'all' | 'issues' | 'human' | 'compliant';

	let openMap = $state<Record<string, boolean>>({});
	let filter = $state<Filter>('all');

	let version = $derived($activeVersion);
	let sectionsList = $derived(version?.sections ?? []);
	let themesList = $derived(version?.themes ?? []);
	let results = $derived($activeReview?.results ?? {});

	// Collapsed by default: (re)initialise the open map whenever the checklist
	// version changes. Sections start closed; the user opens what they want.
	let lastVersionId = '';
	$effect(() => {
		const id = version?.id ?? '';
		if (id !== lastVersionId) {
			lastVersionId = id;
			openMap = version ? initOpenMap(version) : {};
		}
	});

	let scoreResult = $derived(version ? computeScores(version, results) : null);
	let counts = $derived(
		version
			? countResults(version, results)
			: { compliant: 0, 'non-compliant': 0, human: 0, pending: 0, total: 0 }
	);
	let byTheme = $derived.by(() => {
		const out: Record<string, Section[]> = {};
		themesList.forEach((t) => (out[t.id] = []));
		sectionsList.forEach((s) => out[s.theme]?.push(s));
		return out;
	});

	function rOf(sec: Section, it: ChecklistItemDef): ItemResult {
		return results[it.id] ?? { result: 'pending' };
	}

	function itemMatchesFilter(sec: Section, it: ChecklistItemDef): boolean {
		const r = rOf(sec, it).result;
		if (filter === 'all') return true;
		if (filter === 'issues') return r === 'non-compliant';
		if (filter === 'human') return r === 'human';
		if (filter === 'compliant') return r === 'compliant';
		return true;
	}

	function sectionVisibleItems(sec: Section): ChecklistItemDef[] {
		return sec.items.filter((it) => itemMatchesFilter(sec, it));
	}

	function themeHasVisible(themeId: string): Section[] {
		return (byTheme[themeId] ?? []).filter((sec) =>
			sec.items.some((it) => itemMatchesFilter(sec, it))
		);
	}

	function sectionCounts(sec: Section): Record<string, number> {
		return sec.items.reduce(
			(a, it) => {
				const r = rOf(sec, it).result;
				a[r] = (a[r] || 0) + 1;
				return a;
			},
			{} as Record<string, number>
		);
	}

	function setOpen(id: string, v: boolean) {
		openMap = { ...openMap, [id]: v };
	}
	function expandAll() {
		openMap = version ? initOpenMap(version, true) : {};
	}
	function collapseAll() {
		openMap = version ? initOpenMap(version, false) : {};
	}

	function pickItem(sec: Section, it: ChecklistItemDef) {
		picked.set({ sectionId: sec.id, n: it.n });
		drawerOpen.set(true);
	}

	// A critical gap click: reveal the PRP group, then open the item drawer.
	function pickGap(sectionId: string, n: number) {
		openMap = { ...openMap, [sectionId]: true };
		picked.set({ sectionId, n });
		drawerOpen.set(true);
	}

	function selectedKey(sec: Section, it: ChecklistItemDef): boolean {
		const p = $picked;
		return !!p && p.sectionId === sec.id && p.n === it.n;
	}
</script>

<div class="pl-brand-line"></div>
<div class="review">
	<ReviewSummaryBand onPickGap={pickGap} />

	<!-- Filters -->
	<div class="review-toolbar">
		<button class="chip" class:active={filter === 'all'} aria-pressed={filter === 'all'} onclick={() => (filter = 'all')} type="button">
			All <span class="count">{counts.total}</span>
		</button>
		<button class="chip" class:active={filter === 'issues'} aria-pressed={filter === 'issues'} onclick={() => (filter = 'issues')} type="button">
			<Icon name="alert" size={12} /> Non-Compliant <span class="count">{counts['non-compliant'] || 0}</span>
		</button>
		<button class="chip" class:active={filter === 'human'} aria-pressed={filter === 'human'} onclick={() => (filter = 'human')} type="button">
			<Icon name="user" size={12} /> Needs Human <span class="count">{counts.human || 0}</span>
		</button>
		<button class="chip" class:active={filter === 'compliant'} aria-pressed={filter === 'compliant'} onclick={() => (filter = 'compliant')} type="button">
			<Icon name="check" size={12} stroke={3} /> Compliant <span class="count">{counts.compliant || 0}</span>
		</button>
		<div style="flex:1"></div>
		<button class="btn btn-sm btn-ghost" onclick={expandAll} type="button"><Icon name="chevD" size={12} /> Expand all</button>
		<button class="btn btn-sm btn-ghost" onclick={collapseAll} type="button"><Icon name="chevR" size={12} /> Collapse</button>
	</div>

	<!-- Themes -->
	{#each themesList as theme (theme.id)}
		{@const visibleSecs = themeHasVisible(theme.id)}
		{#if visibleSecs.length > 0}
			{@const themeData = scoreResult?.themeRows.find((t) => t.id === theme.id)}
			{#if themeData}
				<div class="theme">
					<div class="theme-head">
						<h2>
							<span class="theme-id {theme.id.toLowerCase()}">{theme.id}</span>
							{theme.name}
							{#if theme.gate}<span class="gate-tag">MANDATORY GATE</span>{/if}
						</h2>
						<div class="theme-stats">
							<span><b>{themeData.pct}%</b> score</span>
							<span>{themeData.yes}/{themeData.total} compliant</span>
							{#if themeData.human}<span>{themeData.human} human</span>{/if}
							<span><b>{theme.weight}%</b> weight</span>
						</div>
					</div>

					{#each visibleSecs as sec (sec.id)}
						{@const items = sectionVisibleItems(sec)}
						{#if items.length > 0 || filter === 'all'}
							{@const isOpen = openMap[sec.id] === true}
							{@const c = sectionCounts(sec)}
							<div class="section" class:open={isOpen}>
								<button class="sec-head" aria-expanded={isOpen} aria-controls="sec-{sec.id}" onclick={() => setOpen(sec.id, !isOpen)} type="button">
									<div class="left">
										<span class="chev"><Icon name="chevR" size={14} /></span>
										<div class="titleblock">
											<div class="prp">{sec.id} · {sec.codes}</div>
											<h3>{sec.title}</h3>
											<div class="intent">{sec.intent}</div>
										</div>
									</div>
									<div class="right">
										{#if c.compliant}<span class="minibadge ok"><span class="dot"></span>{c.compliant}</span>{/if}
										{#if c['non-compliant']}<span class="minibadge bad"><span class="dot"></span>{c['non-compliant']}</span>{/if}
										{#if c.human}<span class="minibadge warn"><span class="dot"></span>{c.human}</span>{/if}
									</div>
								</button>

								{#if isOpen}
									<div class="sec-body" id="sec-{sec.id}">
										{#each items as it (it.n)}
											{@const ans = rOf(sec, it)}
											<button class="item-row" class:selected={selectedKey(sec, it)} onclick={() => pickItem(sec, it)} type="button">
												<div class="item-num">{itemNumber(sec.id, it.n)}</div>
												<div class="item-status"><StatusCircle result={ans.result} /></div>
												<div class="item-text">
													{it.text}
													<div class="meta">
														<span>{it.codes}</span>
														{#if ans.confidence != null && ans.result !== 'human'}
															<span class="conf">confidence {Math.round(ans.confidence * 100)}%</span>
														{/if}
														{#if ans.reviewed}<span style="color:var(--primary)">· deep-reviewed</span>{/if}
														{#if ans.edited}<span style="color:var(--ink-500)">· edited</span>{/if}
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
