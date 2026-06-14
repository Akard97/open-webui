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

// Internal OE approval lifecycle: an OE reviewer submits a completed review,
// then an OE approver approves & publishes (or rejects). No external body.
export type ApprovalStatus = 'idle' | 'pending' | 'approved' | 'rejected';
export interface ApprovalState {
	status: ApprovalStatus;
	sentAt: string | null;
	decidedAt: string | null;
	decidedBy: string | null;
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

	// Library-redesign additions. All optional so the workflow-side stores
	// (which still use this shape) keep working.
	summary?: string | null;
	outline?: string[] | null;
	effectiveDate?: string | null;
	related?: string[]; // codes of related policies (same function)
}

export type Stage = 'upload' | 'scanning' | 'review';
export type ViewKey = 'all-policies' | 'new-review';
