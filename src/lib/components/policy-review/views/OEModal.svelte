<script lang="ts">
	// OE submission modal — collects a cover note and submits the review.
	// Port of OEModal from the design's oe.jsx.

	import Icon from '../ui/Icon.svelte';
	import { POLICY_META } from '../lib/mocks';
	import { oeModalOpen, submitToOE } from '../lib/store';

	let note = $state(
		'Submitting v1.3 of the Digital City Asset Disposal Policy for OE approval. Reviewer override notes attached.'
	);

	function close() {
		oeModalOpen.set(false);
	}

	function submit() {
		submitToOE(note);
		close();
	}
</script>

<div
	class="modal-overlay"
	class:open={$oeModalOpen}
	onclick={close}
	role="presentation"
>
	<div class="modal" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
		<div class="modal-head">
			<h3>Send to Organizational Excellence</h3>
			<p>
				The OE department will receive the full PRP review with all reviewer overrides and decide
				to approve, reject, or return for revision.
			</p>
		</div>
		<div class="modal-body">
			<div class="editor-grid">
				<div>
					<label for="oe-note">Cover note (optional)</label>
					<textarea id="oe-note" bind:value={note}></textarea>
				</div>
				<div style="display:grid; grid-template-columns:1fr 1fr; gap:10px">
					<div>
						<label for="oe-reviewer">Reviewer</label>
						<input
							id="oe-reviewer"
							value={POLICY_META.reviewer}
							readonly
							style="background:var(--bg-soft)"
						/>
					</div>
					<div>
						<label for="oe-recipient">Recipient</label>
						<input
							id="oe-recipient"
							value="OE Department — Policy Governance"
							readonly
							style="background:var(--bg-soft)"
						/>
					</div>
				</div>
			</div>
		</div>
		<div class="modal-foot">
			<button class="btn" onclick={close} type="button">Cancel</button>
			<button class="btn btn-primary" onclick={submit} type="button">
				<Icon name="send" size={13} /> Submit for approval
			</button>
		</div>
	</div>
</div>
