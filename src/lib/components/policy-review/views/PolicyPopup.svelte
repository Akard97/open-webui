<script lang="ts">
	// Policy Library — modal popup shown when a row is clicked.
	// Renders metadata, LLM summary, section outline, and related policies.

	import { onDestroy } from 'svelte';
	import { POLICIES, FN_META } from '../lib/mocks';
	import { policyPopupOpen, selectedPolicy, openPolicyPopup, closePolicyPopup } from '../lib/store';
	import type { LibraryPolicy } from '../lib/types';

	let isOpen = $state(false);
	let policy = $state<LibraryPolicy | null>(null);

	const unsubOpen = policyPopupOpen.subscribe((v) => (isOpen = v));
	const unsubSel = selectedPolicy.subscribe((v) => (policy = v));
	onDestroy(() => {
		unsubOpen();
		unsubSel();
	});

	const fnClass = (id: string) => `pl-fn-${id.toLowerCase()}`;

	const fmtUpdated = (d: number | null | undefined): string => {
		if (d == null) return '—';
		if (d === 0) return 'today';
		if (d === 1) return '1d ago';
		if (d < 7) return `${d}d ago`;
		if (d < 30) return `${Math.round(d / 7)}w ago`;
		if (d < 365) return `${Math.round(d / 30)}mo ago`;
		return `${(d / 365).toFixed(1)}y ago`;
	};

	// Resolve related policies from codes -> full records. Filter to approved
	// and limit to the first 3 for popup density.
	const related = $derived.by<LibraryPolicy[]>(() => {
		if (!policy?.related?.length) return [];
		const byCode = new Map(POLICIES.map((p) => [p.code, p]));
		return policy.related
			.map((c) => byCode.get(c))
			.filter((p): p is LibraryPolicy => !!p && p.status === 'approved')
			.slice(0, 3);
	});

	function onKey(e: KeyboardEvent) {
		if (e.key === 'Escape' && isOpen) {
			e.preventDefault();
			closePolicyPopup();
		}
	}
</script>

<svelte:window onkeydown={onKey} />

<div
	class="pl-popup-backdrop"
	class:open={isOpen}
	onclick={closePolicyPopup}
	role="presentation"
></div>

<div
	class="pl-popup"
	class:open={isOpen}
	role="dialog"
	aria-modal="true"
	aria-labelledby="pl-popup-title"
	aria-hidden={!isOpen}
>
	{#if policy}
		<header class="pl-popup-head">
			<div class="pl-popup-head-top">
				<span class="pl-popup-fn {fnClass(policy.fn)}">
					<span class="sw" aria-hidden="true"></span>
					{FN_META[policy.fn]?.name ?? policy.fn}
				</span>
				<button
					class="pl-popup-x"
					type="button"
					onclick={closePolicyPopup}
					aria-label="Close"
				>×</button>
			</div>
			<h2 id="pl-popup-title">{policy.title}</h2>
			<div class="pl-popup-meta">
				<span class="code"><bdi>{policy.code}</bdi></span>
				<span class="sep" aria-hidden="true">·</span>
				<span>{policy.owner}</span>
				<span class="sep" aria-hidden="true">·</span>
				<span>v{policy.version}</span>
				{#if policy.effectiveDate}
					<span class="sep" aria-hidden="true">·</span>
					<span>Effective <bdi>{policy.effectiveDate}</bdi></span>
				{/if}
				<span class="sep" aria-hidden="true">·</span>
				<span>Updated {fmtUpdated(policy.updatedDays)}</span>
			</div>
		</header>

		<div class="pl-popup-body">
			<section class="pl-popup-sec">
				<div class="pl-popup-sec-l">Summary</div>
				{#if policy.summary}
					<p class="pl-popup-summary">{policy.summary}</p>
				{:else}
					<p class="pl-popup-summary" style="color: var(--ink-500); font-style: italic;">
						Summary not yet available — open the PDF to read the policy.
					</p>
				{/if}
			</section>

			{#if policy.outline && policy.outline.length > 0}
				<section class="pl-popup-sec">
					<div class="pl-popup-sec-l">Sections</div>
					<div class="pl-popup-outline">
						{#each policy.outline as line, i (i)}
							<div class="pl-popup-outline-row">
								<span class="n">{i + 1}.</span>
								<span>{line.replace(/^\s*\d+\.\s*/, '')}</span>
							</div>
						{/each}
					</div>
				</section>
			{/if}

			{#if related.length > 0}
				<section class="pl-popup-sec">
					<div class="pl-popup-sec-l">Related policies</div>
					<div class="pl-popup-related">
						{#each related as r (r.code)}
							<button
								class="pl-popup-related-row"
								type="button"
								onclick={() => openPolicyPopup(r)}
							>
								<div>
									<div class="t">{r.title}</div>
									<div class="c"><bdi>{r.code}</bdi></div>
								</div>
								<span class="arr" aria-hidden="true">→</span>
							</button>
						{/each}
					</div>
				</section>
			{/if}
		</div>

		<footer class="pl-popup-foot">
			<button class="btn btn-sm btn-ghost" type="button">Download</button>
			<span class="grow"></span>
			<button class="btn btn-sm" type="button" onclick={closePolicyPopup}>Close</button>
			<button class="btn btn-sm btn-primary" type="button">Open PDF</button>
		</footer>
	{/if}
</div>
