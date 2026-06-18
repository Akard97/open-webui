<script lang="ts">
	import { onMount } from 'svelte';
	import Icon from '../../ui/Icon.svelte';
	import {
		activeVersion,
		checklistVersions,
		checklistDraft,
		publishDraft as storePublish,
		discardDraft,
		saveDraft,
		startDraft,
		loadVersions,
		reactivateVersion
	} from '../../lib/store';
	import { cloneAsDraft, validateDraft } from '../../lib/checklist';
	import type { ChecklistVersion } from '../../lib/types';
	import ChecklistTab from './ChecklistTab.svelte';
	import ScoringTab from './ScoringTab.svelte';
	import StandardsTab from './StandardsTab.svelte';
	import AccessTab from './AccessTab.svelte';

	type Tab = 'checklist' | 'scoring' | 'standards' | 'access';
	let tab = $state<Tab>('checklist');

	// Full version history (active + archived) for the re-activate control. loadChecklist()
	// only fetches the active version, so the admin view pulls the rest on mount.
	let historyOpen = $state(false);
	let archived = $derived($checklistVersions.filter((v) => v.status === 'archived'));
	onMount(() => {
		void loadVersions();
	});

	// Deeply-reactive working copy. Resume an in-progress draft, else clone active.
	let draft = $state<ChecklistVersion>(
		structuredClone($checklistDraft ?? cloneAsDraft($activeVersion))
	);

	let errors = $state<string[]>([]);
	let toast = $state('');
	let live = $derived(validateDraft(draft));

	function flash(msg: string) {
		toast = msg;
		setTimeout(() => (toast = ''), 2500);
	}

	// Persist the working copy to the backend draft (creating one if needed).
	async function persistDraft() {
		if (!$checklistDraft) await startDraft(); // ensure a backend draft exists to write to
		const snap = $state.snapshot(draft) as ChecklistVersion;
		await saveDraft({
			changeSummary: snap.changeSummary,
			themes: snap.themes,
			sections: snap.sections,
			verdictBands: snap.verdictBands,
			standards: snap.standards
		});
	}

	async function save() {
		await persistDraft();
		errors = [];
		flash('Draft saved');
	}

	async function publish() {
		const v = validateDraft(draft);
		if (!v.ok) {
			errors = v.errors;
			return;
		}
		await persistDraft();
		const res = await storePublish();
		if (res.ok) {
			errors = [];
			draft = cloneAsDraft($activeVersion); // fresh draft off the freshly published version
			flash(`Published ${$activeVersion.label}`);
		} else {
			errors = res.errors;
		}
	}

	async function discard() {
		await discardDraft();
		draft = cloneAsDraft($activeVersion);
		errors = [];
		flash('Draft discarded');
	}

	// Audit-safe revert: re-activate an archived version. Resets the working draft to the
	// newly-active version (discarding unsaved local edits, mirroring post-publish).
	async function reactivate(id: string, label: string) {
		await reactivateVersion(id);
		historyOpen = false;
		draft = cloneAsDraft($activeVersion);
		errors = [];
		flash(`Re-activated ${label}`);
	}

	const TABS: { id: Tab; label: string }[] = [
		{ id: 'checklist', label: 'Checklist' },
		{ id: 'scoring', label: 'Scoring & gates' },
		{ id: 'standards', label: 'Standards & codes' },
		{ id: 'access', label: 'Access' }
	];
</script>

<div class="adm">
	<header class="adm-head">
		<div>
			<div class="adm-eyebrow">Policy Review · Admin</div>
			<h1>Checklist administration</h1>
		</div>
		<div class="adm-actions">
			<span class="adm-ver">{$activeVersion.label} active · editing draft</span>
			<div class="adm-hist-wrap">
				<button class="adm-btn" onclick={() => (historyOpen = !historyOpen)} type="button" aria-expanded={historyOpen}>
					<Icon name="clock" size={13} /> History
				</button>
				{#if historyOpen}
					<div class="adm-hist-backdrop" onclick={() => (historyOpen = false)} role="presentation"></div>
					<div class="adm-hist" role="menu">
						<div class="adm-hist-h">Version history</div>
						<div class="adm-hist-row">
							<div class="adm-hist-info">
								<div><strong>{$activeVersion.label}</strong> <span class="adm-tag active">active</span></div>
								<div class="adm-hist-sub">{$activeVersion.publishedBy ?? '—'}{$activeVersion.publishedAt ? ` · ${$activeVersion.publishedAt}` : ''}</div>
							</div>
						</div>
						{#each archived as v (v.id)}
							<div class="adm-hist-row">
								<div class="adm-hist-info">
									<div><strong>{v.label}</strong> <span class="adm-tag">archived</span></div>
									<div class="adm-hist-sub">{v.publishedBy ?? '—'}{v.publishedAt ? ` · ${v.publishedAt}` : ''}</div>
								</div>
								<button class="adm-btn sm" onclick={() => reactivate(v.id, v.label)} type="button">Re-activate</button>
							</div>
						{/each}
						{#if archived.length === 0}
							<div class="adm-hist-empty">No archived versions yet.</div>
						{/if}
					</div>
				{/if}
			</div>
			<button class="adm-btn" onclick={discard} type="button">Discard</button>
			<button class="adm-btn" onclick={save} type="button">Save draft</button>
			<button class="adm-btn primary" onclick={publish} disabled={!live.ok} type="button">
				<Icon name="check" size={13} /> Publish
			</button>
		</div>
	</header>

	{#if toast}<div class="adm-toast">{toast}</div>{/if}

	{#if errors.length || !live.ok}
		<div class="adm-errors">
			<strong>Resolve before publishing:</strong>
			<ul>
				{#each (errors.length ? errors : live.errors) as e (e)}<li>{e}</li>{/each}
			</ul>
		</div>
	{/if}

	<nav class="adm-tabs">
		{#each TABS as t (t.id)}
			<button class="adm-tab" class:active={tab === t.id} onclick={() => (tab = t.id)} type="button">
				{t.label}
			</button>
		{/each}
	</nav>

	<div class="adm-body">
		{#if tab === 'checklist'}
			<ChecklistTab bind:draft />
		{:else if tab === 'scoring'}
			<ScoringTab bind:draft />
		{:else if tab === 'standards'}
			<StandardsTab bind:draft />
		{:else}
			<AccessTab />
		{/if}
	</div>
</div>

<style>
	.adm { max-width: 1000px; margin: 0 auto; padding: 24px 24px 48px; }
	.adm-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
	.adm-eyebrow { font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-400); }
	.adm-head h1 { font-size: 22px; font-weight: 600; margin-top: 4px; }
	.adm-actions { display: flex; align-items: center; gap: 8px; }
	.adm-ver { font-size: 11.5px; color: var(--ink-500); margin-right: 4px; }
	.adm-btn { display: inline-flex; align-items: center; gap: 5px; font-size: 12.5px; padding: 7px 13px; border-radius: 9px; border: 1px solid var(--ink-200); background: none; cursor: pointer; }
	.adm-btn.primary { background: var(--primary); color: #fff; border-color: var(--primary); }
	.adm-btn.sm { padding: 4px 9px; font-size: 11.5px; }
	.adm-btn:disabled { opacity: 0.5; cursor: not-allowed; }
	.adm-hist-wrap { position: relative; }
	.adm-hist-backdrop { position: fixed; inset: 0; z-index: 40; }
	.adm-hist { position: absolute; right: 0; top: calc(100% + 6px); z-index: 41; width: 300px; max-height: 340px; overflow-y: auto; background: var(--surface, #fff); border: 1px solid var(--ink-200); border-radius: 12px; box-shadow: 0 8px 28px rgba(0,0,0,0.12); padding: 8px; }
	.adm-hist-h { font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-400); padding: 4px 8px 8px; }
	.adm-hist-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 8px; border-radius: 8px; }
	.adm-hist-row:hover { background: var(--ink-50, rgba(0,0,0,0.03)); }
	.adm-hist-info { min-width: 0; font-size: 13px; }
	.adm-hist-sub { font-size: 11px; color: var(--ink-400); margin-top: 2px; }
	.adm-tag { font-size: 10px; padding: 1px 7px; border-radius: 20px; background: var(--ink-100); color: var(--ink-500); }
	.adm-tag.active { background: var(--primary-50); color: var(--primary); }
	.adm-hist-empty { font-size: 12px; color: var(--ink-400); padding: 8px; }
	.adm-toast { margin-top: 12px; font-size: 12.5px; color: var(--ok); }
	.adm-errors { margin-top: 14px; border: 1px solid var(--bad); border-radius: 10px; padding: 10px 14px; font-size: 12.5px; color: var(--bad); }
	.adm-errors ul { margin: 6px 0 0; padding-left: 18px; }
	.adm-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--ink-100); margin: 18px 0 0; }
	.adm-tab { background: none; border: 0; border-bottom: 2px solid transparent; padding: 9px 12px; font-size: 13px; color: var(--ink-500); cursor: pointer; }
	.adm-tab.active { color: var(--ink-900); border-bottom-color: var(--primary); font-weight: 500; }
	.adm-body { padding-top: 18px; }
</style>
