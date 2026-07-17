// A widget fence glued to the end of the previous line never parses as a code
// block (fences must start at a line start), and its closing ``` then swallows
// the rest of the message into a stray code block. Models split answers into
// blocks around tool calls/thinking and may start a block directly with
// ```widget; break such a fence onto its own line. Only text outside an open
// code fence is touched, so widget examples inside code blocks stay verbatim.
export function healWidgetFences(content: string): string {
	if (!content.includes('```widget')) return content;
	let inFence = false;
	const healed = content.split('\n').map((line) => {
		if (!inFence) {
			const idx = line.search(/(?!^)```widget(-html)?\b/);
			if (idx > 0) {
				line = line.slice(0, idx) + '\n\n' + line.slice(idx);
			}
		}
		for (const seg of line.split('\n')) {
			if (/^ {0,3}(```|~~~)/.test(seg)) inFence = !inFence;
		}
		return line;
	});
	return healed.join('\n');
}
