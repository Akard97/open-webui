<script lang="ts">
	import { onMount } from 'svelte';
	import Icon from '../../ui/Icon.svelte';
	import {
		activeVersion,
		checklistDraft,
		publishDraft as storePublish,
		discardDraft
	} from '../../lib/store';
	import { cloneAsDraft, validateDraft } from '../../lib/checklist';
	import type { ChecklistVersion } from '../../lib/types';
	import ChecklistTab from './ChecklistTab.svelte';
	import ScoringTab from './ScoringTab.svelte';
	import StandardsTab from './StandardsTab.svelte';
	import AccessTab from './AccessTab.svelte';

	type Tab = 'checklist' | 'scoring' | 'standards' | 'access';
	let tab = $state<Tab>('checklist');

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

	function save() {
		checklistDraft.set($state.snapshot(draft) as ChecklistVersion);
		errors = [];
		flash('Draft saved');
	}

	function publish() {
		const v = validateDraft(draft);
		if (!v.ok) {
			errors = v.errors;
			return;
		}
		checklistDraft.set($state.snapshot(draft) as ChecklistVersion);
		const res = storePublish();
		if (res.ok) {
			errors = [];
			draft = cloneAsDraft($activeVersion); // fresh draft off the freshly published version
			flash(`Published ${$activeVersion.label}`);
		} else {
			errors = res.errors;
		}
	}

	function discard() {
		discardDraft();
		draft = cloneAsDraft($activeVersion);
		errors = [];
		flash('Draft discarded');
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
			<ChecklistTab {draft} />
		{:else if tab === 'scoring'}
			<ScoringTab {draft} />
		{:else if tab === 'standards'}
			<StandardsTab {draft} />
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
	.adm-btn:disabled { opacity: 0.5; cursor: not-allowed; }
	.adm-toast { margin-top: 12px; font-size: 12.5px; color: var(--ok); }
	.adm-errors { margin-top: 14px; border: 1px solid var(--bad); border-radius: 10px; padding: 10px 14px; font-size: 12.5px; color: var(--bad); }
	.adm-errors ul { margin: 6px 0 0; padding-left: 18px; }
	.adm-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--ink-100); margin: 18px 0 0; }
	.adm-tab { background: none; border: 0; border-bottom: 2px solid transparent; padding: 9px 12px; font-size: 13px; color: var(--ink-500); cursor: pointer; }
	.adm-tab.active { color: var(--ink-900); border-bottom-color: var(--primary); font-weight: 500; }
	.adm-body { padding-top: 18px; }
</style>
