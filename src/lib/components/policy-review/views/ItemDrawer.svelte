<script lang="ts">
	// Item drawer — verdict, comment, reference, re-review, manual edit.
	// Port of drawer.jsx from the PRP-2 design handoff.

	import Icon from '../ui/Icon.svelte';
	import StatusCircle from '../ui/StatusCircle.svelte';
	import {
		sections,
		picked,
		drawerOpen,
		updateItem,
		markReviewed
	} from '../lib/store';
	import type { ChecklistItem, ItemResult, Section } from '../lib/types';

	type Mode = 'view' | 'edit' | 'thinking';

	const RESULT_OPTIONS: { value: ItemResult; label: string }[] = [
		{ value: 'compliant', label: 'Compliant' },
		{ value: 'non-compliant', label: 'Non-Compliant' },
		{ value: 'human', label: 'Needs Human Verification' }
	];

	const DEEP_REVIEW_STEPS = [
		'Re-reading the relevant policy section in full context…',
		'Cross-checking referenced clauses against ISO 9001:2015 and the Osool Metapolicy…',
		'Searching the rest of the document for related provisions and contradictions…',
		'Comparing language against the Osool standard terminology dictionary…',
		'Weighing evidence — confirmed verdict and refining the citation.'
	];

	let mode = $state<Mode>('view');
	let thinkStep = $state(0);
	let draftResult = $state<ItemResult>('compliant');
	let draftComment = $state('');
	let draftRefSection = $state('');
	let draftRefQuote = $state('');

	let section = $derived.by<Section | null>(() => {
		const p = $picked;
		if (!p) return null;
		return $sections.find((s) => s.id === p.sectionId) ?? null;
	});

	let item = $derived.by<ChecklistItem | null>(() => {
		const p = $picked;
		if (!p || !section) return null;
		return section.items.find((x) => x.n === p.n) ?? null;
	});

	// Reset drawer state whenever the picked item changes.
	let prevKey = '';
	$effect(() => {
		const key = item ? `${section?.id}-${item.n}` : '';
		if (key !== prevKey) {
			prevKey = key;
			if (item) {
				draftResult = item.result;
				draftComment = item.comment ?? '';
				draftRefSection = item.ref?.section ?? '';
				draftRefQuote = item.ref?.quote ?? '';
				mode = 'view';
				thinkStep = 0;
			}
		}
	});

	// Deep-review animation.
	$effect(() => {
		if (mode !== 'thinking') return;
		if (!section || !item) return;
		if (thinkStep >= DEEP_REVIEW_STEPS.length) {
			const sid = section.id;
			const n = item.n;
			const t = setTimeout(() => {
				markReviewed(sid, n);
				mode = 'view';
			}, 800);
			return () => clearTimeout(t);
		}
		const t = setTimeout(() => {
			thinkStep = thinkStep + 1;
		}, 700);
		return () => clearTimeout(t);
	});

	function close() {
		drawerOpen.set(false);
	}

	function saveEdit() {
		if (!section || !item) return;
		updateItem(section.id, item.n, {
			result: draftResult,
			comment: draftComment,
			ref: draftRefQuote ? { section: draftRefSection, quote: draftRefQuote } : null,
			edited: true
		});
		mode = 'view';
	}

	function verdictCls(r: ItemResult | undefined): string {
		if (r === 'compliant') return 'ok';
		if (r === 'non-compliant') return 'bad';
		if (r === 'human') return 'warn';
		return '';
	}
</script>

{#if !item || !section}
	<div class="drawer-overlay" class:open={$drawerOpen} onclick={close} role="presentation"></div>
	<div class="drawer" class:open={$drawerOpen}></div>
{:else}
	<div class="drawer-overlay" class:open={$drawerOpen} onclick={close} role="presentation"></div>
	<aside class="drawer" class:open={$drawerOpen}>
		<div class="drawer-head">
			<div style="min-width:0; flex:1">
				<div class="crumb">{section.theme} · {section.id} · Item {item.n}</div>
				<h2>{item.text.replace(' [H]', '')}</h2>
				<div style="display:flex; gap:8px; margin-top:8px; align-items:center; flex-wrap:wrap">
					<span style="font-family:var(--mono); font-size:11px; color:var(--ink-400)">
						{item.code}
					</span>
					{#if item.confidence != null && item.result !== 'human'}
						<span style="font-family:var(--mono); font-size:11px; color:var(--ink-500)">
							· confidence {Math.round(item.confidence * 100)}%
						</span>
					{/if}
					{#if item.reviewed}
						<span class="minibadge" style="background:var(--primary-50); color:var(--primary)">
							<Icon name="sparkle" size={10} /> Deep-reviewed
						</span>
					{/if}
					{#if item.edited}
						<span class="minibadge" style="background:var(--ink-100); color:var(--ink-600)">
							Edited by reviewer
						</span>
					{/if}
				</div>
			</div>
			<button class="sb-icon-btn" onclick={close} title="Close" type="button">
				<Icon name="x" size={18} />
			</button>
		</div>

		<div class="drawer-body">
			{#if mode === 'thinking'}
				<div class="thinking">
					<div class="head"><div class="spinner"></div> Re-reviewing with deep analysis</div>
					<ul>
						{#each DEEP_REVIEW_STEPS.slice(0, thinkStep + 1) as s, i (i)}
							<li style="animation-delay: {i * 0.05}s">{s}</li>
						{/each}
					</ul>
				</div>
			{/if}

			{#if mode === 'view'}
				<div class="verdict-row {verdictCls(item.result)}">
					<div class="left">
						<StatusCircle result={item.result} size={32} />
						<div>
							{#if item.result === 'compliant'}
								Compliant
								<div class="sub">Met</div>
							{:else if item.result === 'non-compliant'}
								Non-Compliant
								<div class="sub">Not met</div>
							{:else if item.result === 'human'}
								Needs Human Verification
								<div class="sub">Routed to reviewer</div>
							{:else}
								Pending
							{/if}
						</div>
					</div>
					<button class="btn btn-sm btn-ghost" onclick={() => (mode = 'edit')} type="button">
						<Icon name="pencil" size={12} /> Override
					</button>
				</div>

				<div class="drawer-section">
					<h5>AI Comment</h5>
					<div class="comment-box">
						{#if item.comment}
							{item.comment}
						{:else}
							<em style="color:var(--ink-400)">No comment.</em>
						{/if}
					</div>
				</div>

				<div class="drawer-section">
					<h5>Reference from Policy</h5>
					{#if item.ref}
						<div class="ref-card">
							<div class="src"><Icon name="book" size={11} /> {item.ref.section}</div>
							<blockquote>"{item.ref.quote}"</blockquote>
						</div>
					{:else}
						<div class="comment-box" style="color:var(--ink-500); font-style:italic">
							{#if item.result === 'human'}
								Not applicable — this item requires human verification.
							{:else if item.result === 'non-compliant'}
								No supporting reference — the policy is missing this provision.
							{:else}
								No reference cited.
							{/if}
						</div>
					{/if}
				</div>

				<div class="drawer-section">
					<h5>Re-review with Deep Analysis</h5>
					<div class="deep-action">
						<div class="copy">
							Run a slower, more thorough re-review of this item — the AI will re-read the full
							policy section, cross-check related provisions, and confirm or revise its verdict.
						</div>
						<button
							class="btn btn-primary btn-sm"
							onclick={() => {
								mode = 'thinking';
								thinkStep = 0;
							}}
							type="button"
						>
							<Icon name="sparkle" size={12} /> Re-review
						</button>
					</div>
				</div>
			{/if}

			{#if mode === 'edit'}
				<div class="drawer-section">
					<h5>Override verdict</h5>
					<div class="editor-grid">
						<div>
							<label for="pr-result">Result</label>
							<select id="pr-result" bind:value={draftResult}>
								{#each RESULT_OPTIONS as o (o.value)}
									<option value={o.value}>{o.label}</option>
								{/each}
							</select>
						</div>
						<div>
							<label for="pr-comment">Comment</label>
							<textarea id="pr-comment" bind:value={draftComment}></textarea>
						</div>
						<div>
							<label for="pr-ref-section">Reference section</label>
							<input
								id="pr-ref-section"
								bind:value={draftRefSection}
								placeholder="e.g. §6.4, p.14"
							/>
						</div>
						<div>
							<label for="pr-ref-quote">Reference quote</label>
							<textarea
								id="pr-ref-quote"
								bind:value={draftRefQuote}
								placeholder="Quoted text from the policy"
							></textarea>
						</div>
					</div>
				</div>
			{/if}
		</div>

		<div class="drawer-foot">
			<div style="font-size:11.5px; color:var(--ink-500)">
				<span class="kbd">←</span> <span class="kbd">→</span> next item ·
				<span class="kbd">esc</span> close
			</div>
			<div style="display:flex; gap:8px">
				{#if mode === 'edit'}
					<button class="btn btn-sm" onclick={() => (mode = 'view')} type="button">Cancel</button>
					<button class="btn btn-primary btn-sm" onclick={saveEdit} type="button">
						<Icon name="check" size={12} stroke={3} /> Save override
					</button>
				{:else if mode === 'view'}
					<button class="btn btn-sm btn-ghost" onclick={close} type="button">Close</button>
				{/if}
			</div>
		</div>
	</aside>
{/if}
