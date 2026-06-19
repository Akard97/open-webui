<script lang="ts">
	// New-review entry screen. Collects policy metadata + the policy document and
	// creates a review (multipart upload + synchronous parse) via the backend API.

	import Icon from '../ui/Icon.svelte';
	import { activeVersion, createReview } from '../lib/store';
	import { validateUploadFile, ACCEPT_ATTR, MAX_UPLOAD_MB } from '../lib/uploadValidation';
	import type { PolicyMeta } from '../lib/types';

	let dragging = $state(false);
	let submitting = $state(false);
	let phase = $state<'' | 'uploading' | 'parsing'>('');
	let error = $state('');

	// Selected file.
	let file = $state<File | null>(null);
	let fileInput: HTMLInputElement;

	// Metadata form state.
	let name = $state('');
	let code = $state('');
	let version = $state('');
	let owner = $state('');
	let reviewer = $state('');
	let reviewDate = $state('');
	let pages = $state<number>(0);

	let canSubmit = $derived(
		name.trim().length > 0 && code.trim().length > 0 && file !== null && !submitting
	);

	function pickFile(f: File | null) {
		error = '';
		if (!f) {
			file = null;
			return;
		}
		const msg = validateUploadFile(f);
		if (msg) {
			error = msg;
			file = null;
			return;
		}
		file = f;
	}

	function onFileChange(e: Event) {
		const input = e.target as HTMLInputElement;
		pickFile(input.files?.[0] ?? null);
	}

	function clearFile() {
		file = null;
		error = '';
		if (fileInput) fileInput.value = '';
	}

	function fmtSize(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	async function submit(e: Event) {
		e.preventDefault();
		if (!canSubmit || !file) return;
		submitting = true;
		error = '';
		phase = 'uploading';
		const meta: PolicyMeta = {
			name: name.trim(),
			code: code.trim(),
			version: version.trim(),
			owner: owner.trim(),
			reviewer: reviewer.trim(),
			reviewDate: reviewDate,
			pages: Number(pages) || 0,
			filename: file.name
		};
		try {
			phase = 'parsing';
			await createReview(meta, file); // navigates to the workspace via stage='review'
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
			submitting = false;
			phase = '';
		}
	}

	const HUES = [200, 30, 165, 0, 280, 130];
	let themes = $derived(
		($activeVersion?.themes ?? []).map((t, i) => ({
			id: t.id,
			name: t.name,
			count: ($activeVersion?.sections ?? [])
				.filter((s) => s.theme === t.id)
				.reduce((a, s) => a + s.items.length, 0),
			gate: t.gate,
			hue: HUES[i % HUES.length]
		}))
	);
	let total = $derived(themes.reduce((a, t) => a + t.count, 0));

	function onDragOver(e: DragEvent) {
		e.preventDefault();
		dragging = true;
	}
	function onDragLeave() {
		dragging = false;
	}
	function onDrop(e: DragEvent) {
		e.preventDefault();
		dragging = false;
		pickFile(e.dataTransfer?.files?.[0] ?? null);
	}
</script>

<div class="upload-wrap fade-in">
	<div class="upload-header">
		<div class="crumb">
			<span>Workspace</span>
			<Icon name="chevR" size={11} />
			<span>Policy Review</span>
			<Icon name="chevR" size={11} />
			<span class="crumb-now">New review</span>
		</div>
		<h1>Start a policy review</h1>
		<p>
			Register a draft to validate it against the <b>PRP Master Checklist v2.0</b>. Enter the policy
			details below to open a review workspace; you'll assess each checklist item and route it for
			approval.
		</p>
	</div>

	<form class="meta-form upload-card" onsubmit={submit}>
		<div class="mf-grid">
			<label class="mf-field mf-span2">
				<span class="mf-label">Policy name<i class="mf-req">*</i></span>
				<input
					class="mf-input"
					bind:value={name}
					placeholder="e.g. Information Security Policy"
					required
				/>
			</label>
			<label class="mf-field">
				<span class="mf-label">Policy code<i class="mf-req">*</i></span>
				<input class="mf-input" bind:value={code} placeholder="e.g. POL-SEC-001" required />
			</label>
			<label class="mf-field">
				<span class="mf-label">Version</span>
				<input class="mf-input" bind:value={version} placeholder="e.g. v1.0" />
			</label>
			<label class="mf-field">
				<span class="mf-label">Owner</span>
				<input class="mf-input" bind:value={owner} placeholder="Owning function" />
			</label>
			<label class="mf-field">
				<span class="mf-label">Reviewer</span>
				<input class="mf-input" bind:value={reviewer} placeholder="Assigned reviewer" />
			</label>
			<label class="mf-field">
				<span class="mf-label">Review date</span>
				<input class="mf-input" type="date" bind:value={reviewDate} />
			</label>
			<label class="mf-field">
				<span class="mf-label">Pages</span>
				<input class="mf-input" type="number" min="0" bind:value={pages} placeholder="0" />
			</label>
		</div>

		{#if error}
			<div class="mf-error">{error}</div>
		{/if}

		<div class="mf-actions">
			<span class="mf-hint">Fields marked <i class="mf-req">*</i> are required.</span>
			<button class="btn btn-primary" type="submit" disabled={!canSubmit}>
				{#if submitting}
					{phase === 'parsing' ? 'Parsing document…' : 'Uploading…'}
				{:else}
					<Icon name="check" size={14} /> Create review
				{/if}
			</button>
		</div>
	</form>

	<div
		class="dropzone upload-card"
		class:dragging
		class:has-file={file}
		ondragover={onDragOver}
		ondragleave={onDragLeave}
		ondrop={onDrop}
		role="presentation"
	>
		<input
			bind:this={fileInput}
			type="file"
			accept={ACCEPT_ATTR}
			class="dz-input"
			onchange={onFileChange}
		/>
		{#if file}
			<div class="dz-file">
				<Icon name="fileText" size={18} />
				<div class="dz-file-meta">
					<div class="dz-file-name">{file.name}</div>
					<div class="dz-file-size">{fmtSize(file.size)}</div>
				</div>
				<button type="button" class="dz-remove" onclick={clearFile} aria-label="Remove file">
					<Icon name="x" size={14} />
				</button>
			</div>
		{:else}
			<button type="button" class="dz-browse" onclick={() => fileInput?.click()}>
				<div class="dz-doc-badge"><Icon name="upload" size={14} stroke={2.2} /></div>
				<h3>Drag &amp; drop the policy document, or browse</h3>
				<p>Required to start a review.</p>
				<div class="formats">
					<span>.docx</span><i></i><span>.pdf</span><i></i><span>.md</span><i></i><span>.txt</span>
					<i></i><span>max {MAX_UPLOAD_MB}&nbsp;MB</span>
				</div>
			</button>
		{/if}
	</div>

	<div class="checklist-panel">
		<div class="cp-head">
			<div>
				<div class="cp-eyebrow">Validated against</div>
				<div class="cp-title">
					PRP Master Checklist <span class="cp-ver">v2.0</span>
				</div>
			</div>
			<div class="cp-stats">
				<div><b>{total}</b><span>items</span></div>
				<div class="cp-divider"></div>
				<div><b>{themes.length}</b><span>themes</span></div>
				<div class="cp-divider"></div>
				<div><b>{themes.filter((t) => t.gate).length}</b><span>mandatory gates</span></div>
			</div>
		</div>

		<div class="theme-bar">
			{#each themes as t (t.id)}
				<div
					class="theme-seg"
					style="flex: {t.count}; background: oklch(0.92 0.03 {t.hue})"
					title="{t.name} — {t.count} items"
				>
					<span class="seg-code">{t.id}</span>
					<span class="seg-count">{t.count}</span>
					{#if t.gate}
						<span class="seg-gate" title="Mandatory gate">●</span>
					{/if}
				</div>
			{/each}
		</div>

		<div class="theme-grid">
			{#each themes as t (t.id)}
				<div class="theme-card">
					<div class="theme-dot" style="background: oklch(0.62 0.10 {t.hue})"></div>
					<div class="theme-info">
						<div class="theme-name">
							{t.name}
							{#if t.gate}
								<span class="gate-tag"><Icon name="shield" size={10} stroke={2} /> Gate</span>
							{/if}
						</div>
						<div class="theme-meta">
							<span class="theme-code">{t.id}</span>
							<span>{t.count} items</span>
						</div>
					</div>
				</div>
			{/each}
		</div>
	</div>

	<div class="upload-footer">
		<div class="ft-card">
			<div class="ft-label">Standards referenced</div>
			<div class="ft-body">
				<span class="std-chip">ISO 9001:2015</span>
				<span class="std-chip">Osool Metapolicy</span>
				<span class="std-chip">PRP Checklist</span>
			</div>
		</div>
		<div class="ft-card">
			<div class="ft-label">Decision outcomes</div>
			<div class="ft-body" style="gap:8px">
				<span class="outcome ok"><i></i>Approved</span>
				<span class="outcome warn"><i></i>Conditional</span>
				<span class="outcome bad"><i></i>Rejected</span>
			</div>
		</div>
		<div class="ft-card">
			<div class="ft-label">Privacy</div>
			<div class="ft-body" style="color:var(--ink-600); font-size:12.5px; line-height:1.5">
				Documents are processed inside the Osool tenant. Drafts are never used for model training.
			</div>
		</div>
	</div>
</div>

<style>
	.meta-form {
		padding: 22px 24px;
		margin-bottom: 16px;
		text-align: left;
		display: block;
	}
	.mf-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 14px 16px;
	}
	.mf-span2 {
		grid-column: 1 / -1;
	}
	.mf-field {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.mf-label {
		font-size: 12px;
		font-weight: 600;
		color: var(--ink-600);
		letter-spacing: 0.01em;
	}
	.mf-req {
		color: #c0392b;
		font-style: normal;
		margin-left: 2px;
	}
	.mf-input {
		width: 100%;
		padding: 9px 11px;
		font: inherit;
		font-size: 13.5px;
		color: var(--ink-900);
		background: var(--bg);
		border: 1px solid var(--ink-200);
		border-radius: var(--radius-sm);
		outline: none;
		transition: border-color 0.12s, box-shadow 0.12s;
	}
	.mf-input:focus {
		border-color: var(--primary-300);
		box-shadow: 0 0 0 3px var(--primary-50);
	}
	.mf-input::placeholder {
		color: var(--ink-400);
	}
	.mf-error {
		margin-top: 14px;
		padding: 9px 12px;
		font-size: 13px;
		color: #8a2a1f;
		background: #fdecea;
		border: 1px solid #f5c6c0;
		border-radius: var(--radius-sm);
	}
	.mf-actions {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		margin-top: 18px;
	}
	.mf-hint {
		font-size: 12.5px;
		color: var(--ink-500);
	}
	.btn[disabled] {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.dropzone {
		position: relative;
	}
	.dz-input {
		display: none;
	}
	.dz-browse {
		display: block;
		width: 100%;
		background: none;
		border: 0;
		cursor: pointer;
		font: inherit;
		color: inherit;
		text-align: center;
	}
	.dz-file {
		display: flex;
		align-items: center;
		gap: 12px;
		text-align: left;
	}
	.dz-file-meta {
		min-width: 0;
		flex: 1;
	}
	.dz-file-name {
		font-weight: 600;
		color: var(--ink-900);
		font-size: 13.5px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.dz-file-size {
		font-size: 12px;
		color: var(--ink-500);
	}
	.dz-remove {
		background: none;
		border: 0;
		cursor: pointer;
		color: var(--ink-400);
		padding: 4px;
	}
	.dz-remove:hover {
		color: var(--ink-700);
	}
</style>
