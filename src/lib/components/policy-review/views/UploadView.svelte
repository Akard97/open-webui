<script lang="ts">
	// Upload stage — dropzone for the draft policy document.
	// Port of upload.jsx from the PRP-2 design handoff.
	//
	// Mock behaviour: clicking the dropzone or "Choose policy file" advances
	// the stage to "scanning". No real file processing — the real backend
	// will own that when it lands.

	import Icon from '../ui/Icon.svelte';
	import { stage } from '../lib/store';

	let dragging = $state(false);

	function start() {
		stage.set('scanning');
	}

	const themes = [
		{ id: 'GOV', name: 'Governance & Ownership', count: 14, gate: false, hue: 200 },
		{ id: 'SCO', name: 'Scope & Applicability', count: 9, gate: true, hue: 30 },
		{ id: 'PRO', name: 'Procedural Clarity', count: 16, gate: false, hue: 165 },
		{ id: 'CTR', name: 'Controls & Approvals', count: 12, gate: true, hue: 0 },
		{ id: 'RSK', name: 'Risk & Compliance', count: 11, gate: false, hue: 280 },
		{ id: 'REV', name: 'Revision & Lifecycle', count: 8, gate: false, hue: 130 }
	];
	const total = themes.reduce((a, t) => a + t.count, 0);

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
		start();
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
			Upload a draft to validate it against the <b>PRP Master Checklist v2.0</b>. The AI returns a
			verdict per item with comments and cited references; items requiring human judgement are
			routed to you.
		</p>
	</div>

	<div
		class="dropzone upload-card"
		class:dragging
		ondragover={onDragOver}
		ondragleave={onDragLeave}
		ondrop={onDrop}
		onclick={start}
		onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && start()}
		role="button"
		tabindex="0"
	>
		<div class="dz-doc" aria-hidden="true">
			<div class="dz-doc-corner"></div>
			<div class="dz-doc-lines">
				<span style="width:72%"></span>
				<span style="width:90%"></span>
				<span style="width:62%"></span>
				<span style="width:80%"></span>
			</div>
			<div class="dz-doc-badge"><Icon name="upload" size={14} stroke={2.2} /></div>
		</div>
		<h3>Drop a policy document here</h3>
		<p>DOCX, PDF or Markdown · up to 25 MB</p>
		<button
			class="btn btn-primary"
			onclick={(e) => {
				e.stopPropagation();
				start();
			}}
			type="button"
		>
			<Icon name="paperclip" size={14} /> Choose policy file
		</button>
		<div class="formats">
			<span>.docx</span><i></i><span>.pdf</span><i></i><span>.md</span><i></i><span
				>max 25&nbsp;MB</span
			><i></i>
			<span><Icon name="clock" size={11} stroke={2} /> avg 2m 40s</span>
		</div>
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
				<span class="std-chip">OE Checklist</span>
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
