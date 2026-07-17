import { describe, expect, it } from 'vitest';
import { healWidgetFences } from './heal';

describe('healWidgetFences', () => {
	it('breaks a fence glued to the end of a prose line onto its own line', () => {
		const glued = 'Assets [doc-1, sheet]:```widget\n{"type": "kpi"}\n```\n\nMore text.';
		expect(healWidgetFences(glued)).toBe(
			'Assets [doc-1, sheet]:\n\n```widget\n{"type": "kpi"}\n```\n\nMore text.'
		);
	});

	it('heals widget-html fences too', () => {
		const glued = 'Look:```widget-html\n<b>hi</b>\n```';
		expect(healWidgetFences(glued)).toBe('Look:\n\n```widget-html\n<b>hi</b>\n```');
	});

	it('leaves a well-formed fence untouched', () => {
		const ok = 'Summary:\n\n```widget\n{"type": "table"}\n```\n';
		expect(healWidgetFences(ok)).toBe(ok);
	});

	it('leaves fences inside code blocks untouched', () => {
		const doc = 'Example:\n\n```markdown\nprose```widget\n```\n';
		expect(healWidgetFences(doc)).toBe(doc);
	});

	it('leaves content without widget fences untouched', () => {
		const plain = 'Just some ``` code\nand text.';
		expect(healWidgetFences(plain)).toBe(plain);
	});

	it('heals the glued-after-table-row shape from production', () => {
		const glued = '| A | -48.35% |```widget\n{"type": "chart"}\n```';
		expect(healWidgetFences(glued)).toBe('| A | -48.35% |\n\n```widget\n{"type": "chart"}\n```');
	});
});
