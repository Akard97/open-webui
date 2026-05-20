<script lang="ts">
	// OE response banner — shows submission status + simulate buttons.
	// Port of OEBanner from the design's oe.jsx.

	import Icon from '../ui/Icon.svelte';
	import { oeState, simulateOEDecision, resetOE } from '../lib/store';

	const MAP: Record<string, { icon: string; title: (sentAt: string | null, decidedAt: string | null) => string; sub: (sentAt: string | null, decidedAt: string | null) => string }> = {
		pending: {
			icon: 'clock',
			title: () => 'Submitted to OE — awaiting decision',
			sub: (sentAt) => `Sent ${sentAt} to OE Department · Policy Governance team`
		},
		approved: {
			icon: 'check',
			title: () => 'Approved by OE Department',
			sub: (_, decidedAt) =>
				`Approved ${decidedAt} by Mariam Al-Otaibi, Head of Policy Governance`
		},
		rejected: {
			icon: 'x',
			title: () => 'Rejected by OE Department',
			sub: (_, decidedAt) =>
				`Rejected ${decidedAt} — policy must be revised before re-submission`
		},
		returned: {
			icon: 'refresh',
			title: () => 'Returned by OE Department',
			sub: (_, decidedAt) => `Returned ${decidedAt} for clarifications — see comments below`
		}
	};
</script>

{#if $oeState.status !== 'idle'}
	{@const m = MAP[$oeState.status]}
	<div class="oe-banner {$oeState.status}">
		<div class="icon"><Icon name={m.icon} size={18} stroke={2.4} /></div>
		<div>
			<div class="title">{m.title($oeState.sentAt, $oeState.decidedAt)}</div>
			<div class="sub">{m.sub($oeState.sentAt, $oeState.decidedAt)}</div>
			{#if $oeState.note && $oeState.status !== 'pending'}
				<div class="note">"{$oeState.note}"</div>
			{/if}
		</div>
		<div style="display:flex; gap:6px; flex-shrink:0">
			{#if $oeState.status === 'pending'}
				<button class="btn btn-sm" onclick={() => simulateOEDecision('approved')} type="button">
					Simulate approve
				</button>
				<button class="btn btn-sm" onclick={() => simulateOEDecision('returned')} type="button">
					Simulate return
				</button>
				<button class="btn btn-sm" onclick={() => simulateOEDecision('rejected')} type="button">
					Simulate reject
				</button>
			{:else}
				<button class="btn btn-sm btn-ghost" onclick={resetOE} type="button">Reset</button>
			{/if}
		</div>
	</div>
{/if}
