<script lang="ts">
	import type { ChecklistVersion } from '../../lib/types';

	let { draft }: { draft: ChecklistVersion } = $props();

	let weightSum = $derived(draft.themes.reduce((a, t) => a + (Number(t.weight) || 0), 0));
</script>

<div class="sc">
	<section class="sc-card">
		<h2>Verdict thresholds</h2>
		<p class="sc-help">Weighted-score bands. Both mandatory gates must also pass for Approved / Conditional.</p>
		<div class="sc-bands">
			<label>Approved ≥
				<input type="number" min="0" max="100" bind:value={draft.verdictBands.approved} /> %
			</label>
			<label>Conditional ≥
				<input type="number" min="0" max="100" bind:value={draft.verdictBands.conditional} /> %
			</label>
			<span class="sc-note">Below {draft.verdictBands.conditional}% (or a failed gate) → Rejected.</span>
		</div>
	</section>

	<section class="sc-card">
		<div class="sc-card-h">
			<h2>Theme weights &amp; gates</h2>
			<span class="sc-sum" class:bad={Math.round(weightSum) !== 100}>Total {Math.round(weightSum)}% {Math.round(weightSum) === 100 ? '✓' : '(must be 100%)'}</span>
		</div>
		<div class="sc-rows">
			<div class="sc-row sc-head">
				<span>Theme</span><span>Weight %</span><span>Gate</span><span>Gate ≥</span>
			</div>
			{#each draft.themes as t (t.id)}
				<div class="sc-row">
					<span class="sc-name"><b>{t.id}</b> {t.name}</span>
					<input type="number" min="0" max="100" bind:value={t.weight} />
					<label class="sc-toggle"><input type="checkbox" bind:checked={t.gate} /> Mandatory</label>
					<input type="number" min="0" max="100" bind:value={t.threshold} disabled={!t.gate} />
				</div>
			{/each}
		</div>
	</section>
</div>

<style>
	.sc { display: grid; gap: 16px; }
	.sc-card { border: 1px solid var(--ink-100); border-radius: 12px; padding: 16px 18px; }
	.sc-card-h { display: flex; align-items: baseline; justify-content: space-between; }
	.sc-card h2 { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
	.sc-help { font-size: 12px; color: var(--ink-500); margin-bottom: 12px; }
	.sc-bands { display: flex; gap: 18px; align-items: center; flex-wrap: wrap; font-size: 13px; }
	.sc-bands input { width: 64px; }
	.sc-note { font-size: 12px; color: var(--ink-400); }
	.sc-sum { font-size: 12.5px; color: var(--ok); }
	.sc-sum.bad { color: var(--bad); }
	.sc-rows { display: grid; gap: 6px; margin-top: 10px; }
	.sc-row { display: grid; grid-template-columns: 1fr 90px 130px 90px; gap: 10px; align-items: center; font-size: 12.5px; }
	.sc-row.sc-head { font-size: 11px; color: var(--ink-400); text-transform: uppercase; letter-spacing: 0.04em; }
	.sc-name b { font-family: var(--mono); margin-right: 4px; }
	.sc-toggle { display: flex; align-items: center; gap: 6px; font-size: 12px; }
	.sc input[type='number'] { width: 80px; }
</style>
