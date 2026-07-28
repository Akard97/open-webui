// Contenteditable <-> wire-format helpers for the comment composer. Pure DOM
// functions (no Svelte) so they unit-test under jsdom. Wire format is the
// existing mention token: @[Name](mention:ID) — see mentions.ts.

const TOKEN_RE = /@\[([^\]]*)\]\(mention:([^)\s]+)\)/g;

function escapeHtml(s: string): string {
	return s
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;');
}

/** Non-editable inline chip. data-mention-id/-name carry the token payload. */
export function mentionChipHtml(id: string, name: string): string {
	return (
		`<span contenteditable="false" data-mention-id="${escapeHtml(id)}"` +
		` data-mention-name="${escapeHtml(name)}"` +
		` class="wos-mention-chip">@${escapeHtml(name)}</span>`
	);
}

/** Body text -> editor HTML: tokens become chips, newlines become <br>, rest escaped. */
export function bodyToEditorHtml(body: string): string {
	let out = '';
	let last = 0;
	for (const m of (body ?? '').matchAll(TOKEN_RE)) {
		out += escapeHtml(body.slice(last, m.index)).replace(/\n/g, '<br>');
		out += mentionChipHtml(m[2], m[1]);
		last = (m.index ?? 0) + m[0].length;
	}
	out += escapeHtml(body.slice(last)).replace(/\n/g, '<br>');
	return out;
}

/** Editor DOM -> body text. Chips serialize to tokens; DIV/P boundaries and BR
 * become newlines. Result is trimmed. */
export function serializeEditor(root: HTMLElement): string {
	let out = '';
	const walk = (node: Node): void => {
		if (node.nodeType === Node.TEXT_NODE) {
			out += node.textContent ?? '';
			return;
		}
		if (node.nodeType !== Node.ELEMENT_NODE) return;
		const el = node as HTMLElement;
		const id = el.dataset?.mentionId;
		if (id) {
			out += `@[${el.dataset.mentionName ?? ''}](mention:${id})`;
			return;
		}
		if (el.tagName === 'BR') {
			out += '\n';
			return;
		}
		const block = el.tagName === 'DIV' || el.tagName === 'P';
		if (block && out.length && !out.endsWith('\n')) out += '\n';
		el.childNodes.forEach(walk);
	};
	root.childNodes.forEach(walk);
	return out.trim();
}
