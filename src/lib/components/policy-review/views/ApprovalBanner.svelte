<script lang="ts">
	// Approval banner — shows the internal OE approval status. While a review is
	// pending, an OE approver (canApprove) sees the Approve & Publish / Reject
	// actions; the reviewer just sees the awaiting-decision message.

	import Icon from '../ui/Icon.svelte';
	import {
		approval,
		approveAndPublish,
		rejectPolicy,
		resetApproval,
		canApprove
	} from '../lib/store';

	const MAP: Record<
		string,
		{
			icon: string;
			title: () => string;
			sub: (sentAt: string | null, decidedAt: string | null, decidedBy: string | null) => string;
		}
	> = {
		pending: {
			icon: 'clock',
			title: () => 'Submitted for approval — awaiting OE approver',
			sub: (sentAt) => `Submitted ${sentAt} to the OE approver`
		},
		approved: {
			icon: 'check',
			title: () => 'Approved & published',
			sub: (_, decidedAt, decidedBy) =>
				`Approved ${decidedAt}${decidedBy ? ` by ${decidedBy}` : ''} · added to the policy library`
		},
		rejected: {
			icon: 'x',
			title: () => 'Rejected',
			sub: (_, decidedAt, decidedBy) =>
				`Rejected ${decidedAt}${decidedBy ? ` by ${decidedBy}` : ''} — revise and re-review before resubmitting`
		}
	};
</script>

{#if $approval.status !== 'idle'}
	{@const m = MAP[$approval.status]}
	<div class="approval-banner {$approval.status}">
		<div class="icon"><Icon name={m.icon} size={18} stroke={2.4} /></div>
		<div>
			<div class="title">{m.title()}</div>
			<div class="sub">{m.sub($approval.sentAt, $approval.decidedAt, $approval.decidedBy)}</div>
			{#if $approval.note && $approval.status !== 'pending'}
				<div class="note">"{$approval.note}"</div>
			{/if}
		</div>
		<div style="display:flex; gap:6px; flex-shrink:0">
			{#if $approval.status === 'pending'}
				{#if $canApprove}
					<button class="btn btn-sm btn-primary" onclick={() => approveAndPublish()} type="button">
						Approve &amp; Publish
					</button>
					<button class="btn btn-sm" onclick={() => rejectPolicy()} type="button"> Reject </button>
				{/if}
			{:else}
				<button class="btn btn-sm btn-ghost" onclick={resetApproval} type="button">Reset</button>
			{/if}
		</div>
	</div>
{/if}
