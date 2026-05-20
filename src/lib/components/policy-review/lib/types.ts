// Domain model for the Policy Review tool.
// Mirrors the PRP Master Checklist v2.0 data shape consumed by all views.

export type ItemResult = 'compliant' | 'non-compliant' | 'human' | 'pending';

export interface ChecklistItem {
	n: number;
	text: string;
	code: string;
	result: ItemResult;
	comment?: string;
	ref?: { section: string; quote: string } | null;
	confidence?: number;
	reviewed?: boolean;
	edited?: boolean;
}

export interface Section {
	theme: string; // 'T1'..'T6'
	id: string; // 'PRP1'..'PRP29'
	title: string;
	codes: string;
	intent: string;
	items: ChecklistItem[];
}

export interface Theme {
	id: string;
	name: string;
	weight: number;
	gate: boolean;
	threshold?: number;
}

export interface PolicyMeta {
	name: string;
	code: string;
	version: string;
	owner: string;
	reviewer: string;
	reviewDate: string;
	pages: number;
	filename: string;
}

export type VerdictKey = 'draft' | 'approved' | 'conditional' | 'rejected';
export interface Verdict {
	key: VerdictKey;
	label: string;
	reason: string;
}

export type OEStatus = 'idle' | 'pending' | 'approved' | 'returned' | 'rejected';
export interface OEState {
	status: OEStatus;
	sentAt: string | null;
	decidedAt: string | null;
	note: string;
}

export type PolicyStatus =
	| 'approved'
	| 'in-review'
	| 'pending'
	| 'draft'
	| 'rejected'
	| 'expiring'
	| 'overdue';

export interface LibraryPolicy {
	code: string;
	title: string;
	fn: string;
	owner: string;
	version: string;
	status: PolicyStatus;
	score: number | null;
	pages: number;
	nextReview: string;
	updatedDays: number | null;
	current?: boolean;
}

export type Stage = 'upload' | 'scanning' | 'review';
export type ViewKey = 'all-policies' | 'new-review';
