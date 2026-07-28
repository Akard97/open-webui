<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { Button } from '$lib/components/ui/button';
	import { directory, postComment, editComment, uploadFiles } from '../../lib/store';
	import { avatarColors } from '../../lib/avatar';
	import { bodyToEditorHtml, mentionChipHtml, serializeEditor } from '../../lib/richText';

	export let taskId: string;
	export let placeholder = 'Write a comment…';
	export let compact = false;
	export let allowImages = true;
	export let initialBody = '';
	export let submitLabel = 'Comment';
	export let parentId: string | null = null;
	export let mode: 'create' | 'edit' = 'create';
	export let commentId: string | null = null;
	export let onSubmitted: (() => void) | null = null;
	export let onCancel: (() => void) | null = null;
	export let autofocus = false;

	let editor: HTMLDivElement;
	let fileInput: HTMLInputElement;
	let pending: File[] = [];
	let pendingUrls: string[] = [];
	let busy = false;
	let empty = !initialBody;

	// ── mention typeahead ──
	let taOpen = false;
	let taQuery = '';
	let taIndex = 0;
	let taRange: Range | null = null; // covers the "@query" text being replaced

	$: members = Object.entries($directory).map(([id, u]) => ({ id, name: u.name }));
	$: taMatches = members
		.filter((m) => m.name.toLowerCase().includes(taQuery.toLowerCase()))
		.slice(0, 6);
	$: if (taOpen && taIndex >= taMatches.length) taIndex = 0;

	export function focus(): void {
		editor?.focus();
	}

	function syncEmpty(): void {
		empty = !(editor?.textContent ?? '').trim() && !editor?.querySelector('[data-mention-id]');
	}

	/** Find an "@query" run ending at the caret; open/refresh the typeahead for it. */
	function detectMention(): void {
		const sel = window.getSelection();
		if (!sel || !sel.rangeCount || !sel.isCollapsed) return void (taOpen = false);
		const node = sel.anchorNode;
		if (!node || node.nodeType !== Node.TEXT_NODE || !editor.contains(node)) {
			taOpen = false;
			return;
		}
		const text = (node.textContent ?? '').slice(0, sel.anchorOffset);
		const at = text.lastIndexOf('@');
		// "@" must start the text or follow whitespace, and the query has no spaces.
		if (at === -1 || (at > 0 && !/\s/.test(text[at - 1])) || /\s/.test(text.slice(at + 1))) {
			taOpen = false;
			return;
		}
		taQuery = text.slice(at + 1);
		const r = document.createRange();
		r.setStart(node, at);
		r.setEnd(node, sel.anchorOffset);
		taRange = r;
		taIndex = 0;
		taOpen = true;
	}

	function pickMention(m: { id: string; name: string }): void {
		if (!taRange) return;
		taRange.deleteContents();
		const frag = document.createRange().createContextualFragment(mentionChipHtml(m.id, m.name) + ' ');
		const lastChild = frag.lastChild as ChildNode;
		taRange.insertNode(frag);
		// caret after the inserted space
		const sel = window.getSelection();
		if (sel && lastChild) {
			const r = document.createRange();
			r.setStartAfter(lastChild);
			r.collapse(true);
			sel.removeAllRanges();
			sel.addRange(r);
		}
		taOpen = false;
		taRange = null;
		syncEmpty();
		editor.focus();
	}

	function onKeydown(e: KeyboardEvent): void {
		if (taOpen) {
			if (e.key === 'ArrowDown') { e.preventDefault(); taIndex = (taIndex + 1) % Math.max(1, taMatches.length); return; }
			if (e.key === 'ArrowUp') { e.preventDefault(); taIndex = (taIndex - 1 + Math.max(1, taMatches.length)) % Math.max(1, taMatches.length); return; }
			if (e.key === 'Enter' && taMatches.length) { e.preventDefault(); pickMention(taMatches[taIndex]); return; }
			if (e.key === 'Escape') { e.stopPropagation(); taOpen = false; return; }
		}
		if (e.key === 'Escape' && onCancel) {
			e.stopPropagation(); // keep the task drawer open (subtask-panel lesson)
			onCancel();
			return;
		}
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			void submit();
		}
	}

	function onPaste(e: ClipboardEvent): void {
		e.preventDefault();
		const text = e.clipboardData?.getData('text/plain') ?? '';
		document.execCommand('insertText', false, text);
	}

	function onFiles(e: Event): void {
		const files = (e.target as HTMLInputElement).files;
		if (files) {
			for (const f of Array.from(files)) {
				if (!f.type.startsWith('image/')) continue;
				pending = [...pending, f];
				pendingUrls = [...pendingUrls, URL.createObjectURL(f)];
			}
		}
		(e.target as HTMLInputElement).value = '';
	}

	function removePending(i: number): void {
		URL.revokeObjectURL(pendingUrls[i]);
		pending = pending.filter((_, x) => x !== i);
		pendingUrls = pendingUrls.filter((_, x) => x !== i);
	}

	async function submit(): Promise<void> {
		const body = serializeEditor(editor);
		if ((!body && !pending.length) || busy) return;
		busy = true;
		try {
			if (mode === 'edit' && commentId) {
				await editComment(commentId, body);
			} else {
				const saved = await postComment(taskId, body || '…', parentId ?? undefined);
				if (pending.length) await uploadFiles(taskId, pending, saved.id);
			}
			editor.innerHTML = '';
			pendingUrls.forEach((u) => URL.revokeObjectURL(u));
			pending = [];
			pendingUrls = [];
			syncEmpty();
			onSubmitted?.();
		} finally {
			busy = false;
		}
	}

	import { onMount } from 'svelte';
	onMount(() => {
		if (initialBody) editor.innerHTML = bodyToEditorHtml(initialBody);
		syncEmpty();
		if (autofocus) editor.focus();
	});
</script>

<div class="relative">
	{#if taOpen && taMatches.length}
		<div class="absolute bottom-full left-0 z-20 mb-1.5 w-60 rounded-xl border border-gray-200 bg-white p-1 shadow-lg dark:border-gray-800 dark:bg-gray-900">
			{#each taMatches as m, i (m.id)}
				<button
					class="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left {i === taIndex ? 'bg-primary/10' : 'hover:bg-gray-100 dark:hover:bg-gray-800'}"
					onmousedown={(e) => { e.preventDefault(); pickMention(m); }}
				>
					<span class="flex size-6 flex-none items-center justify-center rounded-full text-[10px] font-bold"
						style="background:{avatarColors(m.id).background};color:{avatarColors(m.id).foreground}">
						{m.name.slice(0, 2).toUpperCase()}
					</span>
					<span class="text-sm font-medium">{m.name}</span>
				</button>
			{/each}
		</div>
	{/if}

	<div class="rounded-xl border border-gray-200 bg-white transition-shadow focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/15 dark:border-gray-800 dark:bg-gray-950">
		<div
			bind:this={editor}
			contenteditable="true"
			role="textbox"
			tabindex="0"
			aria-multiline="true"
			aria-label={placeholder}
			data-placeholder={placeholder}
			class="wos-composer-input max-h-48 overflow-y-auto px-3 py-2.5 text-sm leading-relaxed outline-none {compact ? 'min-h-9' : 'min-h-16'}"
			oninput={() => { syncEmpty(); detectMention(); }}
			onkeydown={onKeydown}
			onpaste={onPaste}
			onclick={detectMention}
		></div>

		{#if pending.length}
			<div class="flex gap-2 px-3 pb-2">
				{#each pendingUrls as url, i (url)}
					<span class="relative size-[52px] overflow-hidden rounded-lg border border-gray-200 dark:border-gray-800">
						<img src={url} alt="" class="size-full object-cover" />
						<button
							class="absolute right-0.5 top-0.5 flex size-4 items-center justify-center rounded-full bg-black/55 text-white"
							title="Remove image" onclick={() => removePending(i)}
						><Icon name="x" size={10} /></button>
					</span>
				{/each}
			</div>
		{/if}

		<div class="flex items-center gap-1 border-t border-gray-100 px-2 py-1.5 dark:border-gray-900">
			{#if allowImages}
				<Button variant="ghost" size="icon-sm" class="text-gray-400" title="Attach image"
					onclick={() => fileInput.click()}><Icon name="image" size={15} /></Button>
				<input type="file" accept="image/*" multiple class="hidden" bind:this={fileInput} onchange={onFiles} />
			{/if}
			<span class="ml-1 hidden text-[11px] text-gray-400 sm:block">
				Enter to send · Shift+Enter for new line · @ to mention
			</span>
			<div class="flex-1"></div>
			{#if onCancel}
				<Button variant="ghost" size="sm" onclick={() => onCancel?.()}>Cancel</Button>
			{/if}
			<Button size="sm" disabled={empty && !pending.length} onclick={() => void submit()}>
				{busy ? '…' : submitLabel}
			</Button>
		</div>
	</div>
</div>

<style>
	.wos-composer-input:empty::before {
		content: attr(data-placeholder);
		color: rgb(156 163 175);
		pointer-events: none;
	}
	:global(.wos-mention-chip) {
		display: inline;
		border-radius: 6px;
		padding: 0 4px;
		font-weight: 600;
		color: var(--primary);
		background: color-mix(in srgb, var(--primary) 10%, transparent);
		white-space: nowrap;
	}
</style>
