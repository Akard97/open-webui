<script lang="ts">
	// Approval banner — shows the internal OE approval status. While a review is
	// pending, an OE approver (canApprove) sees the Approve & Publish / Reject
	// actions; the reviewer just sees the awaiting-decision message.

	import Icon from '../ui/Icon.svelte';
	import {
		activeReview,
		approveAndPublish,
		rejectPolicy,
		canApprove
	} from '../lib/store';

	let approval = $derived($activeReview?.approval ?? null);
	let approvalError = $state('');
	let rejectOpen = $state(false);
	let rejectNote = $state('');

	async function approve() {
		if (!$activeReview) return;
		approvalError = '';
		try {
			await approveAndPublish($activeReview.id);
		} catch (e) {
			approvalError = String(e);
		}
	}

	function openReject() {
		approvalError = '';
		rejectOpen = true;
	}

	function cancelReject() {
		rejectOpen = false;
		rejectNote = '';
		approvalError = '';
	}

	// The approver's note is required by the backend; the disabled Confirm button
	// keeps us from ever reaching that 400 from the UI.
	async function confirmReject() {
		if (!$activeReview || !rejectNote.trim()) return;
		approvalError = '';
		try {
			await rejectPolicy($activeReview.id, rejectNote.trim());
			rejectOpen = false;
			rejectNote = '';
		} catch (e) {
			approvalError = String(e);
		}
	}

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

{#if approval && approval.status !== 'idle'}
	{@const m = MAP[approval.status]}
	<div class="approval-banner {approval.status}">
		<div class="icon"><Icon name={m.icon} size={18} stroke={2.4} /></div>
		<div>
			<div class="title">{m.title()}</div>
			<div class="sub">{m.sub(approval.sentAt, approval.decidedAt, approval.decidedBy)}</div>
			{#if approval.note && approval.status !== 'pending'}
				<div class="note">"{approval.note}"</div>
			{/if}
			{#if approvalError}
				<div class="error">{approvalError}</div>
			{/if}
			{#if rejectOpen}
				<div class="editor-grid reject-form">
					<div>
						<label for="reject-note">Rejection note (required)</label>
						<textarea
							id="reject-note"
							bind:value={rejectNote}
							placeholder="Explain what the reviewer needs to change before resubmitting…"
						></textarea>
					</div>
					<div class="reject-actions">
						<button class="btn btn-sm" onclick={cancelReject} type="button">Cancel</button>
						<button
							class="btn btn-sm btn-danger"
							onclick={confirmReject}
							disabled={!rejectNote.trim()}
							type="button"
						>
							Confirm rejection
						</button>
					</div>
				</div>
			{/if}
		</div>
		<div style="display:flex; gap:6px; flex-shrink:0">
			{#if approval.status === 'pending'}
				{#if $canApprove}
					<button class="btn btn-sm btn-primary" onclick={approve} type="button">
						Approve &amp; Publish
					</button>
					{#if !rejectOpen}
						<button class="btn btn-sm" onclick={openReject} type="button"> Reject </button>
					{/if}
				{/if}
			{:else if $activeReview?.status === 'rejected'}
				<!-- No reset affordance in normal flow; rejected policy must go through a new review cycle -->
			{/if}
		</div>
	</div>
{/if}
