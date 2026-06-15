<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import type { ChecklistVersion } from '../../lib/types';
	import { blankItem, blankSection, blankTheme, nextItemN } from '../../lib/checklist';

	let { draft }: { draft: ChecklistVersion } = $props();

	let open = $state<Record<string, boolean>>({});
	function toggle(id: string) { open = { ...open, [id]: !(open[id] ?? true) }; }
	function isOpen(id: string) { return open[id] ?? true; }

	function sectionsOf(themeId: string) {
		return draft.sections.filter((s) => s.theme === themeId);
	}
	function addItem(sectionId: string) {
		const sec = draft.sections.find((s) => s.id === sectionId);
		if (sec) sec.items.push(blankItem(sectionId, nextItemN(sec)));
	}
	function removeItem(sectionId: string, itemId: string) {
		const sec = draft.sections.find((s) => s.id === sectionId);
		if (sec) sec.items = sec.items.filter((i) => i.id !== itemId);
	}
	function addSection(themeId: string) {
		const id = `PRP${Date.now().toString().slice(-5)}`; // unique-enough id for a draft node
		draft.sections.push(blankSection(themeId, id));
	}
	function removeSection(sectionId: string) {
		draft.sections = draft.sections.filter((s) => s.id !== sectionId);
	}
	function addTheme() {
		// Collision-proof id = one past the highest existing T-number. A length-based
		// id collides after a theme is removed (drop T3 from T1–T6 → length 5 → "T6"
		// duplicate), which crashes the keyed {#each}.
		const maxN = draft.themes.reduce((m, t) => {
			const n = Number(t.id.replace(/^T/, ''));
			return Number.isFinite(n) ? Math.max(m, n) : m;
		}, 0);
		draft.themes.push(blankTheme(`T${maxN + 1}`));
	}
	function removeTheme(themeId: string) {
		draft.themes = draft.themes.filter((t) => t.id !== themeId);
		draft.sections = draft.sections.filter((s) => s.theme !== themeId);
	}
</script>

<div class="ct">
	{#each draft.themes as theme (theme.id)}
		<div class="ct-theme">
			<div class="ct-theme-h">
				<button class="ct-chev" onclick={() => toggle(theme.id)} type="button">
					<Icon name={isOpen(theme.id) ? 'chevD' : 'chevR'} size={14} />
				</button>
				<span class="ct-tid">{theme.id}</span>
				<input class="ct-name" bind:value={theme.name} aria-label="Theme name" />
				{#if theme.gate}<span class="ct-gate">GATE</span>{/if}
				<span class="ct-meta">{theme.weight}% · {sectionsOf(theme.id).reduce((a, s) => a + s.items.length, 0)} items</span>
				<button class="ct-del" onclick={() => removeTheme(theme.id)} type="button" title="Remove theme">
					<Icon name="trash" size={13} />
				</button>
			</div>

			{#if isOpen(theme.id)}
				<div class="ct-sections">
					{#each sectionsOf(theme.id) as sec (sec.id)}
						<div class="ct-sec">
							<div class="ct-sec-h">
								<input class="ct-sec-title" bind:value={sec.title} aria-label="Group title" />
								<input class="ct-sec-codes" bind:value={sec.codes} placeholder="codes (e.g. ISO Cl.4.1 · OEC)" aria-label="Group codes" />
								<button class="ct-del" onclick={() => removeSection(sec.id)} type="button" title="Remove group">
									<Icon name="trash" size={13} />
								</button>
							</div>
							<input class="ct-sec-intent" bind:value={sec.intent} placeholder="What this group assesses" aria-label="Group intent" />

							<div class="ct-items">
								{#each sec.items as item (item.id)}
									<div class="ct-item">
										<span class="ct-itnum">{sec.id.replace('PRP', '')}.{item.n}</span>
										<textarea class="ct-ittext" bind:value={item.text} rows="1" aria-label="Requirement text"></textarea>
										<input class="ct-itcodes" bind:value={item.codes} placeholder="codes" aria-label="Item codes" />
										<div class="ct-assess">
											<button
												class="ct-seg"
												class:on={item.assessment === 'auto'}
												onclick={() => (item.assessment = 'auto')}
												type="button">Auto</button>
											<button
												class="ct-seg"
												class:on={item.assessment === 'human'}
												onclick={() => (item.assessment = 'human')}
												type="button">Human</button>
										</div>
										<button class="ct-del" onclick={() => removeItem(sec.id, item.id)} type="button" title="Remove item">
											<Icon name="x" size={13} />
										</button>
									</div>
								{/each}
								<button class="ct-add" onclick={() => addItem(sec.id)} type="button">
									<Icon name="plus" size={12} /> Add item
								</button>
							</div>
						</div>
					{/each}
					<button class="ct-add group" onclick={() => addSection(theme.id)} type="button">
						<Icon name="plus" size={12} /> Add PRP group
					</button>
				</div>
			{/if}
		</div>
	{/each}
	<button class="ct-add theme" onclick={addTheme} type="button">
		<Icon name="plus" size={12} /> Add theme
	</button>
</div>

<style>
	.ct { display: grid; gap: 12px; }
	.ct-theme { border: 1px solid var(--ink-100); border-radius: 12px; overflow: hidden; }
	.ct-theme-h { display: flex; align-items: center; gap: 8px; padding: 10px 12px; background: var(--ink-50, rgba(0,0,0,0.02)); }
	.ct-chev { background: none; border: 0; cursor: pointer; color: var(--ink-500); display: flex; }
	.ct-tid { font-family: var(--mono); font-size: 12px; color: var(--ink-500); }
	.ct-name { flex: 1; min-width: 0; font-size: 13.5px; font-weight: 500; border: 1px solid transparent; border-radius: 6px; padding: 3px 6px; background: none; }
	.ct-name:focus { border-color: var(--ink-200); background: #fff; outline: none; }
	.ct-gate { font-size: 10px; color: var(--bad); background: color-mix(in srgb, var(--bad) 12%, transparent); padding: 2px 6px; border-radius: 5px; }
	.ct-meta { font-size: 11.5px; color: var(--ink-400); }
	.ct-del { background: none; border: 0; color: var(--ink-400); cursor: pointer; display: flex; padding: 3px; }
	.ct-del:hover { color: var(--bad); }
	.ct-sections { padding: 10px 12px; display: grid; gap: 10px; }
	.ct-sec { border: 1px solid var(--ink-100); border-radius: 10px; padding: 10px; display: grid; gap: 7px; }
	.ct-sec-h { display: flex; gap: 8px; align-items: center; }
	.ct-sec-title { flex: 1; font-size: 12.5px; font-weight: 500; border: 1px solid var(--ink-100); border-radius: 6px; padding: 5px 7px; }
	.ct-sec-codes { width: 220px; font-size: 11.5px; font-family: var(--mono); border: 1px solid var(--ink-100); border-radius: 6px; padding: 5px 7px; }
	.ct-sec-intent { font-size: 12px; color: var(--ink-600); border: 1px solid var(--ink-100); border-radius: 6px; padding: 5px 7px; }
	.ct-items { display: grid; gap: 6px; }
	.ct-item { display: flex; gap: 8px; align-items: flex-start; }
	.ct-itnum { font-family: var(--mono); font-size: 11px; color: var(--ink-400); padding-top: 7px; min-width: 30px; }
	.ct-ittext { flex: 1; font-size: 12.5px; border: 1px solid var(--ink-100); border-radius: 6px; padding: 6px 8px; resize: vertical; font-family: inherit; }
	.ct-itcodes { width: 110px; font-size: 11px; font-family: var(--mono); border: 1px solid var(--ink-100); border-radius: 6px; padding: 6px 8px; }
	.ct-assess { display: flex; }
	.ct-seg { font-size: 11px; padding: 5px 9px; border: 1px solid var(--ink-200); background: none; cursor: pointer; }
	.ct-seg:first-child { border-radius: 6px 0 0 6px; }
	.ct-seg:last-child { border-radius: 0 6px 6px 0; border-left: 0; }
	.ct-seg.on { background: var(--primary); color: #fff; border-color: var(--primary); }
	.ct-add { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--primary); background: none; border: 1px dashed var(--ink-200); border-radius: 8px; padding: 6px 10px; cursor: pointer; justify-self: start; }
	.ct-add.theme { margin-top: 4px; }
</style>
