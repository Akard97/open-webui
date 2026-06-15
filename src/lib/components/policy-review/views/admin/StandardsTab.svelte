<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import type { ChecklistVersion } from '../../lib/types';

	let { draft = $bindable() }: { draft: ChecklistVersion } = $props();

	function add() {
		draft.standards.push({ code: 'NEW', label: 'New standard', description: '' });
	}
	function remove(i: number) {
		draft.standards = draft.standards.filter((_, idx) => idx !== i);
	}
</script>

<div class="st">
	<p class="st-help">
		The controlled vocabulary of standard codes that checklist items are tagged against
		(used in the Code column of the published checklist).
	</p>
	<div class="st-list">
		{#each draft.standards as s, i (i)}
			<div class="st-row">
				<input class="st-code" bind:value={s.code} aria-label="Code" />
				<div class="st-fields">
					<input class="st-label" bind:value={s.label} placeholder="Label" aria-label="Label" />
					<input class="st-desc" bind:value={s.description} placeholder="Description" aria-label="Description" />
				</div>
				<button class="st-del" onclick={() => remove(i)} type="button" title="Remove">
					<Icon name="trash" size={13} />
				</button>
			</div>
		{/each}
	</div>
	<button class="st-add" onclick={add} type="button"><Icon name="plus" size={12} /> Add standard</button>
</div>

<style>
	.st { display: grid; gap: 12px; }
	.st-help { font-size: 12.5px; color: var(--ink-500); }
	.st-list { display: grid; gap: 8px; }
	.st-row { display: flex; gap: 10px; align-items: flex-start; border: 1px solid var(--ink-100); border-radius: 10px; padding: 10px; }
	.st-code { width: 72px; font-family: var(--mono); font-size: 12.5px; font-weight: 500; border: 1px solid var(--ink-100); border-radius: 6px; padding: 6px 8px; }
	.st-fields { flex: 1; display: grid; gap: 6px; }
	.st-label { font-size: 12.5px; font-weight: 500; border: 1px solid var(--ink-100); border-radius: 6px; padding: 6px 8px; }
	.st-desc { font-size: 12px; color: var(--ink-600); border: 1px solid var(--ink-100); border-radius: 6px; padding: 6px 8px; }
	.st-del { background: none; border: 0; color: var(--ink-400); cursor: pointer; padding: 6px; }
	.st-del:hover { color: var(--bad); }
	.st-add { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--primary); background: none; border: 1px dashed var(--ink-200); border-radius: 8px; padding: 6px 10px; cursor: pointer; justify-self: start; }
</style>
