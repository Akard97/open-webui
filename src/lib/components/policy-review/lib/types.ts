// Domain model for the Policy Review tool.
// Two aggregate roots: a versioned checklist DEFINITION, and per-policy REVIEWS
// that snapshot a checklist version and hold the answers.

// ─── Checklist definition (versioned) ──────────────────────────────────────

export type Assessment = 'auto' | 'human';

export interface ChecklistItemDef {
	id: string; // stable, e.g. 'PRP1-3'
	n: number; // display number within the PRP group
	text: string; // requirement text (no ' [H]' suffix)
	codes: string; // e.g. 'OEC, ISO'
	assessment: Assessment; // 'human' => routed to a person, AI leaves it blank
}

export interface Section {
	// A PRP group.
	id: string; // 'PRP1'..'PRP29'
	theme: string; // 'T1'..'T6'
	title: string;
	codes: string; // e.g. 'ISO Cl.4.1, 4.2 · OEC · OM'
	intent: string;
	items: ChecklistItemDef[];
}

export interface Theme {
	id: string; // 'T1'..'T6'
	name: string;
	weight: number; // percent
	gate: boolean;
	threshold: number; // gate pass threshold, percent
}

export interface VerdictBands {
	approved: number; // default 85
	conditional: number; // default 70
}

export interface StandardCode {
	code: string; // e.g. 'OEC'
	label: string; // e.g. 'Organizational Excellence Checklist'
	description: string;
}

export type ChecklistStatus = 'active' | 'draft' | 'archived';

export interface ChecklistVersion {
	id: string; // 'v2.0'
	label: string; // 'v2.0'
	status: ChecklistStatus;
	publishedAt: string | null;
	publishedBy: string | null;
	changeSummary: string;
	themes: Theme[];
	sections: Section[];
	verdictBands: VerdictBands;
	standards: StandardCode[];
}

// ─── Review (per policy) ───────────────────────────────────────────────────

export type ItemVerdict = 'compliant' | 'non-compliant' | 'human' | 'pending';

export interface ItemResult {
	result: ItemVerdict;
	comment?: string;
	ref?: { section: string; quote: string } | null;
	confidence?: number;
	reviewed?: boolean;
	edited?: boolean;
}

export type ReviewStatus = 'draft' | 'pending' | 'approved' | 'rejected';

// Internal OE approval lifecycle (maker-checker). No external body.
export type ApprovalStatus = 'idle' | 'pending' | 'approved' | 'rejected';
export interface ApprovalState {
	status: ApprovalStatus;
	sentAt: string | null;
	decidedAt: string | null;
	decidedBy: string | null;
	note: string;
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

export interface Review {
	id: string;
	policyMeta: PolicyMeta;
	checklistVersionId: string; // snapshot taken when the review was created
	checklistSnapshot?: ChecklistVersion; // pinned copy returned by the backend
	results: Record<string, ItemResult>; // keyed by ChecklistItemDef.id
	status: ReviewStatus;
	approval: ApprovalState;
	strengths: string[];
	createdBy: string;
	createdAt: string;
}

export type VerdictKey = 'draft' | 'approved' | 'conditional' | 'rejected';
export interface Verdict {
	key: VerdictKey;
	label: string;
	reason: string;
}

// ─── Library ────────────────────────────────────────────────────────────────

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
	summary?: string | null;
	outline?: string[] | null;
	effectiveDate?: string | null;
	related?: string[];
}

// Transient view/stage keys (unchanged in Plan 1; expanded in Plan 2).
export type Stage = 'upload' | 'scanning' | 'review';
export type ViewKey = 'overview' | 'library' | 'new-review' | 'my-reviews' | 'approvals' | 'review' | 'admin';
