<script lang="ts">
	// Item drawer — verdict, comment, reference, re-review, manual edit.

	import Icon from '../ui/Icon.svelte';
	import StatusCircle from '../ui/StatusCircle.svelte';
	import {
		activeVersion,
		activeReview,
		picked,
		drawerOpen,
		updateItemResult,
		markReviewed
	} from '../lib/store';
	import type { ChecklistItemDef, ItemVerdict, ItemResult, Section } from '../lib/types';

	type Mode = 'view' | 'edit' | 'thinking';

	const RESULT_OPTIONS: { value: ItemVerdict; label: string }[] = [
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
	let draftResult = $state<ItemVerdict>('compliant');
	let draftComment = $state('');
	let draftRefSection = $state('');
	let draftRefQuote = $state('');
	let drawerEl: HTMLElement | undefined = $state();

	let section = $derived.by<Section | null>(() => {
		const p = $picked;
		if (!p) return null;
		return $activeVersion?.sections.find((s) => s.id === p.sectionId) ?? null;
	});

	let def = $derived.by<ChecklistItemDef | null>(() => {
		const p = $picked;
		if (!p || !section) return null;
		return section.items.find((x) => x.n === p.n) ?? null;
	});

	let answer = $derived<ItemResult>(
		def && $activeReview ? ($activeReview.results[def.id] ?? { result: 'pending' }) : { result: 'pending' }
	);
	let verdict = $derived<ItemVerdict>(answer.result);

	let prevKey = '';
	$effect(() => {
		const key = def ? def.id : '';
		if (key !== prevKey) {
			prevKey = key;
			if (def) {
				// 'pending' isn't an overridable verdict — default the editor to
				// 'human' so saving never writes an unresolved verdict back.
				draftResult = answer.result === 'pending' ? 'human' : answer.result;
				draftComment = answer.comment ?? '';
				draftRefSection = answer.ref?.section ?? '';
				draftRefQuote = answer.ref?.quote ?? '';
				mode = 'view';
				thinkStep = 0;
			}
		}
	});

	$effect(() => {
		if (mode !== 'thinking') return;
		if (!def || !$activeReview) return;
		if (thinkStep >= DEEP_REVIEW_STEPS.length) {
			const rid = $activeReview.id;
			const iid = def.id;
			const t = setTimeout(() => {
				markReviewed(rid, iid);
				mode = 'view';
			}, 800);
			return () => clearTimeout(t);
		}
		const t = setTimeout(() => {
			thinkStep = thinkStep + 1;
		}, 700);
		return () => clearTimeout(t);
	});

	// While open: lock background scroll, move focus into the drawer, and trap
	// Tab inside it. Restore focus to the previously-focused element on close.
	$effect(() => {
		if (!$drawerOpen || !drawerEl) return;
		const el = drawerEl;
		const prevActive = document.activeElement as HTMLElement | null;
		const prevOverflow = document.body.style.overflow;
		document.body.style.overflow = 'hidden';

		const focusables = () =>
			Array.from(
				el.querySelectorAll<HTMLElement>(
					'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
				)
			).filter((node) => !node.hasAttribute('disabled'));

		focusables()[0]?.focus();

		function onKeydown(e: KeyboardEvent) {
			if (e.key !== 'Tab') return;
			const els = focusables();
			if (els.length === 0) return;
			const first = els[0];
			const last = els[els.length - 1];
			if (e.shiftKey && document.activeElement === first) {
				e.preventDefault();
				last.focus();
			} else if (!e.shiftKey && document.activeElement === last) {
				e.preventDefault();
				first.focus();
			}
		}
		el.addEventListener('keydown', onKeydown);

		return () => {
			el.removeEventListener('keydown', onKeydown);
			document.body.style.overflow = prevOverflow;
			prevActive?.focus?.();
		};
	});

	function close() {
		drawerOpen.set(false);
	}

	function saveEdit() {
		if (!def || !$activeReview) return;
		updateItemResult($activeReview.id, def.id, {
			result: draftResult,
			comment: draftComment,
			ref: draftRefQuote ? { section: draftRefSection, quote: draftRefQuote } : null,
			edited: true
		});
		mode = 'view';
	}

	function verdictCls(r: ItemVerdict | undefined): string {
		if (r === 'compliant') return 'ok';
		if (r === 'non-compliant') return 'bad';
		if (r === 'human') return 'warn';
		return '';
	}
</script>

{#if !def || !section}
	<div class="drawer-overlay" class:open={$drawerOpen} onclick={close} role="presentation"></div>
	<div class="drawer" class:open={$drawerOpen}></div>
{:else}
	<div class="drawer-overlay" class:open={$drawerOpen} onclick={close} role="presentation"></div>
	<div
		class="drawer"
		class:open={$drawerOpen}
		role="dialog"
		aria-modal="true"
		aria-labelledby="pr-drawer-title"
		bind:this={drawerEl}
	>
		<div class="drawer-head">
			<div style="min-width:0; flex:1">
				<div class="crumb">{section.theme} · {section.id} · Item {def.n}</div>
				<h2 id="pr-drawer-title">{def.text}</h2>
				<div style="display:flex; gap:8px; margin-top:8px; align-items:center; flex-wrap:wrap">
					<span style="font-family:var(--mono); font-size:11px; color:var(--ink-400)">
						{def.codes}
					</span>
					{#if answer.confidence != null && verdict !== 'human'}
						<span style="font-family:var(--mono); font-size:11px; color:var(--ink-500)">
							· confidence {Math.round(answer.confidence * 100)}%
						</span>
					{/if}
					{#if answer.reviewed}
						<span class="minibadge" style="background:var(--primary-50); color:var(--primary)">
							<Icon name="sparkle" size={10} /> Deep-reviewed
						</span>
					{/if}
					{#if answer.edited}
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
				<div class="verdict-row {verdictCls(verdict)}">
					<div class="left">
						<StatusCircle result={verdict} size={32} />
						<div>
							{#if verdict === 'compliant'}
								Compliant
								<div class="sub">Met</div>
							{:else if verdict === 'non-compliant'}
								Non-Compliant
								<div class="sub">Not met</div>
							{:else if verdict === 'human'}
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
						{#if answer.comment}
							{answer.comment}
						{:else}
							<em style="color:var(--ink-400)">No comment.</em>
						{/if}
					</div>
				</div>

				<div class="drawer-section">
					<h5>Reference from Policy</h5>
					{#if answer.ref}
						<div class="ref-card">
							<div class="src"><Icon name="book" size={11} /> {answer.ref.section}</div>
							<blockquote>"{answer.ref.quote}"</blockquote>
						</div>
					{:else}
						<div class="comment-box" style="color:var(--ink-500); font-style:italic">
							{#if verdict === 'human'}
								Not applicable — this item requires human verification.
							{:else if verdict === 'non-compliant'}
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
	</div>
{/if}
