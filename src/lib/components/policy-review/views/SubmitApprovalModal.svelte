<script lang="ts">
	// Submit-for-approval modal — an OE reviewer hands the completed review to an
	// OE approver, with an optional note. Internal to OE (maker-checker).

	import Icon from '../ui/Icon.svelte';
	import { submitModalOpen, submitForApproval, activeReview } from '../lib/store';

	let note = $state('Reviewer override notes attached for the approver.');
	let submitError = $state('');

	function close() {
		submitModalOpen.set(false);
	}

	async function submit() {
		if (!$activeReview) return;
		submitError = '';
		try {
			await submitForApproval($activeReview.id, note);
			close();
		} catch (e) {
			submitError = String(e);
		}
	}
</script>

<div
	class="modal-overlay"
	class:open={$submitModalOpen}
	onclick={close}
	role="presentation"
>
	<div class="modal" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
		<div class="modal-head">
			<h3>Submit for Approval</h3>
			<p>
				The OE approver will receive the full PRP review with all reviewer overrides and decide
				to approve &amp; publish or reject.
			</p>
		</div>
		<div class="modal-body">
			<div class="editor-grid">
				<div>
					<label for="approval-note">Note to approver (optional)</label>
					<textarea id="approval-note" bind:value={note}></textarea>
				</div>
				<div style="display:grid; grid-template-columns:1fr 1fr; gap:10px">
					<div>
						<label for="approval-reviewer">Reviewer</label>
						<input
							id="approval-reviewer"
							value={$activeReview?.policyMeta?.reviewer ?? ''}
							readonly
							style="background:var(--bg-soft)"
						/>
					</div>
					<div>
						<label for="approval-approver">Approver</label>
						<input
							id="approval-approver"
							value="Organizational Excellence — Approver"
							readonly
							style="background:var(--bg-soft)"
						/>
					</div>
				</div>
			</div>
		</div>
		{#if submitError}
			<p class="modal-error">{submitError}</p>
		{/if}
		<div class="modal-foot">
			<button class="btn" onclick={close} type="button">Cancel</button>
			<button class="btn btn-primary" onclick={submit} type="button">
				<Icon name="send" size={13} /> Submit for Approval
			</button>
		</div>
	</div>
</div>
