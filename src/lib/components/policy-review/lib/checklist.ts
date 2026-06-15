// Pure helpers for the checklist draft → publish lifecycle.
// No store/IO here — the store wires these in.

import type { ChecklistVersion, ChecklistItemDef, Section, Theme } from './types';

export interface ValidationResult {
	ok: boolean;
	errors: string[];
}

export function cloneAsDraft(active: ChecklistVersion): ChecklistVersion {
	const draft = structuredClone(active);
	draft.status = 'draft';
	draft.publishedAt = null;
	draft.publishedBy = null;
	return draft;
}

export function validateDraft(draft: ChecklistVersion): ValidationResult {
	const errors: string[] = [];
	const weightSum = draft.themes.reduce((a, t) => a + (t.weight || 0), 0);
	if (Math.round(weightSum) !== 100) {
		errors.push(`Theme weights must sum to 100% (currently ${Math.round(weightSum)}%).`);
	}
	draft.themes.forEach((t) => {
		const secs = draft.sections.filter((s) => s.theme === t.id);
		if (secs.length === 0) {
			errors.push(`Theme ${t.id} has no PRP groups.`);
		}
		const itemCount = secs.reduce((a, s) => a + s.items.length, 0);
		if (itemCount === 0) {
			errors.push(`Theme ${t.id} has no items.`);
		}
	});
	draft.sections.forEach((s) => {
		if (s.items.length === 0) errors.push(`Group ${s.id} has no items.`);
	});
	return { ok: errors.length === 0, errors };
}

export function nextLabel(label: string): string {
	const m = label.match(/^v(\d+)\.(\d+)$/);
	if (!m) return `${label}.1`;
	return `v${m[1]}.${Number(m[2]) + 1}`;
}

export interface PublishResult {
	versions: ChecklistVersion[];
	published: ChecklistVersion;
}

// Archives every current active version and appends the draft as the new active.
// `now` is injectable so callers control timestamp formatting (and tests stay deterministic).
export function publishDraft(
	versions: ChecklistVersion[],
	draft: ChecklistVersion,
	publishedBy: string,
	now = 'now'
): PublishResult {
	const activeLabel = versions.find((v) => v.status === 'active')?.label ?? draft.label;
	const archived = versions.map((v) =>
		v.status === 'active' ? { ...v, status: 'archived' as const } : v
	);
	const published: ChecklistVersion = {
		...structuredClone(draft),
		label: nextLabel(activeLabel),
		id: nextLabel(activeLabel),
		status: 'active',
		publishedAt: now,
		publishedBy
	};
	return { versions: [...archived, published], published };
}

export function nextItemN(section: Section): number {
	return section.items.reduce((max, it) => Math.max(max, it.n), 0) + 1;
}

export function blankItem(sectionId: string, n: number): ChecklistItemDef {
	return { id: `${sectionId}-${n}`, n, text: 'New requirement', codes: '', assessment: 'auto' };
}

export function blankSection(themeId: string, id: string): Section {
	return {
		id,
		theme: themeId,
		title: 'New PRP group',
		codes: '',
		intent: 'Describe what this group assesses.',
		items: [blankItem(id, 1)]
	};
}

export function blankTheme(id: string): Theme {
	return { id, name: 'New theme', weight: 0, gate: false, threshold: 85 };
}
