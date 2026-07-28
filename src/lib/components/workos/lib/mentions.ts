const MENTION_RE = /@\[[^\]]*\]\(mention:([^)\s]+)\)/g;

export function parseMentions(body: string): string[] {
	const out: string[] = [];
	for (const m of (body ?? '').matchAll(MENTION_RE)) {
		if (!out.includes(m[1])) out.push(m[1]);
	}
	return out;
}

export function mentionToken(id: string, name: string): string {
	return `@[${name}](mention:${id})`;
}

/** Replace mention tokens with fragment links (`[@Name](#mention-ID)`) for markdown
 * rendering. Fragment hrefs survive DOMPurify; CommentItem styles/intercepts them. */
export function renderMentions(body: string, name: (id: string) => string): string {
	return (body ?? '').replace(MENTION_RE, (_full, id) => `[@${name(id)}](#mention-${id})`);
}
