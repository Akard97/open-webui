export type ListColumnKey = 'assignee' | 'start' | 'due' | 'priority' | 'labels' | 'progress';

export interface ListColumnMeta {
	key: ListColumnKey;
	label: string;
}

// Fixed left-to-right order of the optional columns (Name is always first, the row
// menu is always last — neither is configurable).
export const LIST_COLUMNS: ListColumnMeta[] = [
	{ key: 'assignee', label: 'Assignee' },
	{ key: 'start', label: 'Start date' },
	{ key: 'due', label: 'Due date' },
	{ key: 'priority', label: 'Priority' },
	{ key: 'labels', label: 'Labels' },
	{ key: 'progress', label: 'Progress' }
];

export type ColumnPrefs = Record<ListColumnKey, boolean>;

export function defaultColumnPrefs(): ColumnPrefs {
	return { assignee: true, start: true, due: true, priority: true, labels: true, progress: true };
}

// Merge a persisted preference string over the defaults, tolerating missing keys,
// unknown keys, non-boolean values, and malformed JSON (always returns a full set).
export function parseColumnPrefs(raw: string | null): ColumnPrefs {
	const prefs = defaultColumnPrefs();
	if (!raw) return prefs;
	try {
		const parsed = JSON.parse(raw);
		if (!parsed || typeof parsed !== 'object') return prefs;
		for (const { key } of LIST_COLUMNS) {
			if (typeof (parsed as Record<string, unknown>)[key] === 'boolean') {
				prefs[key] = (parsed as Record<string, boolean>)[key];
			}
		}
		return prefs;
	} catch {
		return prefs;
	}
}

const NAME_WIDTH = 'minmax(180px, 1fr)';
const MENU_WIDTH = '36px';
const COLUMN_WIDTH: Record<ListColumnKey, string> = {
	assignee: '120px',
	start: '120px',
	due: '120px',
	priority: '130px',
	labels: '160px',
	progress: '120px'
};

// CSS grid-template-columns for one row: name (flexible) + each visible optional
// column (fixed) + trailing menu column. Header and task rows share this template.
export function gridTemplate(prefs: ColumnPrefs): string {
	const cols = [NAME_WIDTH];
	for (const { key } of LIST_COLUMNS) if (prefs[key]) cols.push(COLUMN_WIDTH[key]);
	cols.push(MENU_WIDTH);
	return cols.join(' ');
}
