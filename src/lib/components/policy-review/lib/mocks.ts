// Mocked PRP Master Checklist v2.0 data + Osool policy library snapshot.
// Verbatim port of the PRP-2 design handoff (data.js + all-policies.jsx).
// Used by every view until the real backend ships.

import type {
	PolicyMeta,
	Theme,
	Section,
	LibraryPolicy,
	PolicyStatus
} from './types';

// ─── Active in-flight policy ───────────────────────────────────────────────

export const POLICY_META: PolicyMeta = {
	name: 'Digital City Asset Disposal Policy',
	code: 'OSOOL-RE-POL-014',
	version: 'v1.3',
	owner: 'Real Estate Investment Division',
	reviewer: 'Ahmad Al-Sayegh',
	reviewDate: 'May 17, 2026',
	pages: 24,
	filename: 'Digital_City_Asset_Disposal_Policy_v1.3.pdf'
};

// ─── PRP themes ────────────────────────────────────────────────────────────

export const THEMES: Theme[] = [
	{ id: 'T1', name: 'Policy Foundation', weight: 28, gate: true, threshold: 85 },
	{ id: 'T2', name: 'Governance and Accountability', weight: 28, gate: true, threshold: 85 },
	{ id: 'T3', name: 'People and Communication', weight: 16, gate: false },
	{ id: 'T4', name: 'Performance and Measurement', weight: 14, gate: false },
	{ id: 'T5', name: 'Implementation and Change', weight: 7, gate: false },
	{ id: 'T6', name: 'Policy Integrity', weight: 7, gate: false }
];

// ─── Sections + checklist items (mocked AI verdicts) ───────────────────────

export const SECTIONS: Section[] = [
	// ── T1 ──
	{
		theme: 'T1',
		id: 'PRP1',
		title: 'Understanding and Context',
		codes: 'ISO Cl.4.1, 4.2 · OEC · OM',
		intent: 'The policy must clearly state what it governs, who it applies to, and why it exists.',
		items: [
			{
				n: 1,
				text: 'The policy states a clear purpose and objective in the Purpose section.',
				code: 'OEC, ISO',
				result: 'compliant',
				comment:
					'Section 1.1 (Purpose) sets out objectives explicitly and references the strategic intent of orderly asset disposal.',
				ref: {
					section: '§1.1 Purpose, p.3',
					quote:
						'This policy establishes the principles and authority for the disposal of digital city assets owned or controlled by Osool, in order to maximize realisable value, ensure transparency, and maintain regulatory compliance.'
				},
				confidence: 0.96
			},
			{
				n: 2,
				text: 'The intended audience is explicitly identified.',
				code: 'OEC, ISO',
				result: 'compliant',
				comment: 'Applicability section names the in-scope entities clearly.',
				ref: {
					section: '§2 Applicability, p.4',
					quote:
						'This policy applies to all Osool subsidiaries, joint ventures, and special-purpose vehicles holding digital city assets, including authorised representatives acting on their behalf.'
				},
				confidence: 0.94
			},
			{
				n: 3,
				text: 'The scope is defined in the Applicability section, including what is covered and what is excluded.',
				code: 'OEC, ISO',
				result: 'non-compliant',
				comment:
					"Inclusions are present but the policy does not enumerate exclusions. Add a 'Not in scope' subsection covering leased and pre-development assets.",
				ref: {
					section: '§2 Applicability, p.4',
					quote:
						'This policy applies to all Osool subsidiaries, joint ventures, and special-purpose vehicles holding digital city assets…'
				},
				confidence: 0.88
			}
		]
	},
	{
		theme: 'T1',
		id: 'PRP2',
		title: 'Clarity and Language',
		codes: 'OEC · OM',
		intent:
			'The policy must be written in plain, consistent, and unambiguous language appropriate for its audience.',
		items: [
			{
				n: 1,
				text: 'The policy uses plain, unambiguous language throughout.',
				code: 'OEC, ISO, OM',
				result: 'compliant',
				comment:
					'Language is concise across §3–§7. A small number of long sentences in §6.4 could be split for readability but do not impede meaning.',
				ref: {
					section: '§3 Definitions, p.5',
					quote:
						'"Digital city asset" means any parcel, building, or development right registered under Osool\'s Digital City master registry.'
				},
				confidence: 0.91
			},
			{
				n: 2,
				text: 'Language is appropriate for the intended audience.',
				code: 'OEC, OM',
				result: 'compliant',
				comment: 'Vocabulary aligns with the audience of asset managers and divisional heads.',
				ref: {
					section: 'throughout',
					quote:
						"Terms such as 'disposal', 'reserve price', and 'fair market value' are used with definitions and align with internal terminology."
				},
				confidence: 0.9
			},
			{
				n: 3,
				text: 'Consistent terminology is used across all sections.',
				code: 'OEC, OM',
				result: 'non-compliant',
				comment:
					"'Reserve Price', 'Floor Price' and 'Minimum Bid' are used interchangeably in §6.2, §6.4, and §8.1. Standardise on one term and update Definitions.",
				ref: {
					section: '§6.2 & §8.1, p.13 & p.16',
					quote:
						'§6.2: "the Reserve Price set by the Pricing Committee"  …  §8.1: "the Floor Price shall not be disclosed to bidders".'
				},
				confidence: 0.93
			},
			{
				n: 4,
				text: 'The policy is free of contradictory or conflicting statements.',
				code: 'OEC',
				result: 'compliant',
				comment:
					'No direct contradictions detected. One borderline tension between §5.3 (manager-led disposals) and §7.1 (Committee approval) is reconciled by the DoA reference.',
				ref: {
					section: '§5.3 & §7.1',
					quote:
						'§5.3 authorises managers to initiate disposal; §7.1 confirms approval flows through DoA thresholds — interpretation is consistent.'
				},
				confidence: 0.85
			},
			{
				n: 5,
				text: "The writing style is consistent with other Osool policies.  [H]",
				code: 'OEC, OM',
				result: 'human',
				comment:
					"Comparison against Osool's policy library requires human judgement — passed to reviewer.",
				ref: null
			},
			{
				n: 6,
				text: "The policy conforms to Osool's standard language and communication approach.  [H]",
				code: 'OEC, OM',
				result: 'human',
				comment:
					'Style adherence assessed by Organizational Excellence — human verification required.',
				ref: null
			}
		]
	},
	{
		theme: 'T1',
		id: 'PRP3',
		title: 'Completeness and Structure',
		codes: 'OEC · OM · ISO Cl.7.5',
		intent:
			"The policy must follow Osool's standard structure, carry a valid document code, and include all mandatory sections.",
		items: [
			{
				n: 1,
				text: 'A definitions or glossary section is present and includes all technical terms and acronyms used in the policy.',
				code: 'OEC',
				result: 'compliant',
				comment:
					'Definitions cover 14 terms. Verified against in-document usage — no orphan acronyms detected.',
				ref: {
					section: '§3 Definitions, p.5–6',
					quote:
						'Defined terms include: Digital City Asset, Reserve Price, Disposal Committee, DoA, Fair Market Value, PSF, Letter of Intent, …'
				},
				confidence: 0.95
			},
			{
				n: 2,
				text: 'References to supporting procedures are included.',
				code: 'OEC',
				result: 'compliant',
				comment: '§11 references three procedure manuals; cross-reference document codes resolve.',
				ref: {
					section: '§11 References, p.21',
					quote:
						'OSOOL-RE-PROC-014-A Disposal Execution Manual; OSOOL-RE-PROC-014-B Pricing & Valuation Procedure; …'
				},
				confidence: 0.97
			},
			{
				n: 3,
				text: 'Access and distribution controls for the document are defined.',
				code: 'ISO',
				result: 'non-compliant',
				comment:
					"Document classification is set to 'Internal' on the cover, but distribution rules and revocation handling are not described.",
				ref: { section: 'Cover page', quote: 'Classification: Internal.' },
				confidence: 0.89
			},
			{
				n: 4,
				text: 'Retention period for the policy and its records is stated.',
				code: 'ISO',
				result: 'non-compliant',
				comment:
					'No retention period stated. Add a clause referencing the Records Management Policy with a minimum 10-year retention for disposal records.',
				ref: null,
				confidence: 0.92
			},
			{
				n: 5,
				text: 'The official Osool Policy Template has been used, ensuring consistent structure and formatting.  [H]',
				code: 'OEC, OM',
				result: 'human',
				comment:
					'Template compliance requires visual inspection against the OEC Master Template — human verification.',
				ref: null
			},
			{
				n: 6,
				text: 'A General Provisions section is present covering communication, training, onboarding, monitoring, and accountability for the policy.',
				code: 'OM',
				result: 'compliant',
				comment:
					'§10 General Provisions covers all five required elements with named responsible parties.',
				ref: {
					section: '§10 General Provisions, p.19',
					quote:
						'Communication, training, onboarding, monitoring, and accountability obligations for this policy rest with the Real Estate Investment Division, supported by HR and OE.'
				},
				confidence: 0.94
			},
			{
				n: 7,
				text: "The policy document code follows Osool's naming and coding convention.",
				code: 'OM',
				result: 'compliant',
				comment: 'Code OSOOL-RE-POL-014 follows the [Org]-[Function]-[Type]-[Number] convention.',
				ref: {
					section: 'Cover page',
					quote: 'Document Code: OSOOL-RE-POL-014  ·  Version 1.3  ·  Effective 01-Jun-2026'
				},
				confidence: 0.99
			},
			{
				n: 8,
				text: 'The policy does not contain procedural detail. Step-by-step procedures, forms, and operational instructions are kept in the supporting procedure manual.',
				code: 'OM',
				result: 'non-compliant',
				comment:
					'§6.3 contains a 9-step disposal procedure that belongs in the procedure manual, not the policy. Move steps to OSOOL-RE-PROC-014-A and keep only the principle.',
				ref: {
					section: '§6.3 Disposal Steps, p.14',
					quote:
						'Step 1 — Asset is flagged for disposal in the registry. Step 2 — Pricing Committee assigns a Reserve Price. Step 3 — Marketing pack is produced within 10 business days. …'
				},
				confidence: 0.96
			}
		]
	},
	{
		theme: 'T1',
		id: 'PRP5',
		title: 'Policy Necessity and Strategic Alignment',
		codes: 'OM · OEC',
		intent:
			"The policy must have a clear rationale and must be aligned to Osool's strategic objectives.",
		items: [
			{
				n: 1,
				text: 'The rationale for why this policy is necessary is documented.  [H]',
				code: 'OM',
				result: 'human',
				comment: 'Strategic rationale assessment requires human judgement.',
				ref: null
			},
			{
				n: 2,
				text: "The policy is aligned to and contributes to Osool's current strategic and operational objectives.  [H]",
				code: 'OEC, OM',
				result: 'human',
				comment: 'Strategic alignment is reviewed by OE leadership.',
				ref: null
			},
			{
				n: 3,
				text: 'The policy identifies the business functions responsible for its implementation.',
				code: 'OM',
				result: 'compliant',
				comment:
					'§4 RACI identifies Real Estate Investment Division as accountable, with Finance and Legal as consulted.',
				ref: {
					section: '§4 Roles & Responsibilities, p.7',
					quote:
						'Accountable: Real Estate Investment Division.  Responsible: Asset Disposal Unit.  Consulted: Finance, Legal, Internal Audit.  Informed: OE.'
				},
				confidence: 0.97
			}
		]
	},
	// ── T2 ──
	{
		theme: 'T2',
		id: 'PRP6',
		title: 'Accountability and Ownership',
		codes: 'ISO Cl.5.1, 5.3 · OEC · OM',
		intent:
			'A named policy owner must be identified. Approval authority must be stated. Access controls must be defined.',
		items: [
			{
				n: 1,
				text: 'A named policy owner is identified.',
				code: 'OEC, ISO, OM',
				result: 'compliant',
				comment: 'Policy owner is named on the cover and in §4.',
				ref: {
					section: 'Cover & §4, p.1, p.7',
					quote: 'Policy Owner: Head of Real Estate Investment Division.'
				},
				confidence: 0.99
			},
			{
				n: 2,
				text: 'The approval authority and authorized signatories for the policy are clearly stated.',
				code: 'OEC, ISO, OM',
				result: 'compliant',
				comment: 'Approval flow references the Board Investment Committee with signatories.',
				ref: {
					section: '§13 Approval, p.22',
					quote:
						'Approved by the Board Investment Committee on 12 April 2026. Signatories: Chairman, CEO, Head of OE.'
				},
				confidence: 0.98
			},
			{
				n: 3,
				text: 'Responsibilities for each role are explicitly defined, not implied.',
				code: 'OEC, ISO',
				result: 'compliant',
				comment: '§4 RACI is explicit with named role responsibilities per stage.',
				ref: {
					section: '§4 Roles & Responsibilities, p.7–8',
					quote:
						'Each role has a one-line responsibility statement covering initiation, valuation, approval, execution, and post-disposal reporting.'
				},
				confidence: 0.94
			},
			{
				n: 4,
				text: 'Authorities are assigned at appropriate levels.  [H]',
				code: 'OEC, ISO',
				result: 'human',
				comment:
					'Authority-level appropriateness must be assessed by the reviewer against DoA.',
				ref: null
			},
			{
				n: 5,
				text: "Senior management demonstrates commitment to and accountability for the policy's effectiveness through formal approval.",
				code: 'OM, ISO',
				result: 'compliant',
				comment: 'Approval record includes signatures from C-suite.',
				ref: {
					section: '§13 Approval, p.22',
					quote:
						'Approved by the Board Investment Committee … Signatories: Chairman, CEO, Head of OE.'
				},
				confidence: 0.95
			},
			{
				n: 6,
				text: 'Restricted or confidential policies are identified, accessible only to authorized parties, and require Governance Function approval for third-party access.',
				code: 'OM',
				result: 'compliant',
				comment:
					'Classification is set to Internal; access list and third-party approval gate documented.',
				ref: {
					section: '§12 Access Control, p.21',
					quote:
						'Third-party access to this policy or its disposal records requires written approval from the Governance Function.'
				},
				confidence: 0.9
			},
			{
				n: 7,
				text: 'The policy does not declare specific approval authorities or thresholds. Approval authorities are referenced through the Delegation of Authority (DoA), not duplicated in the policy.',
				code: 'OM',
				result: 'non-compliant',
				comment:
					'§7.2 specifies SAR-value thresholds for managerial approval that duplicate the DoA. Remove monetary thresholds and reference the DoA instead.',
				ref: {
					section: '§7.2 Approval Thresholds, p.15',
					quote:
						'Disposals up to SAR 5,000,000 may be approved by the Division Head; above this, by the Investment Committee.'
				},
				confidence: 0.97
			},
			{
				n: 8,
				text: 'The policy ensures appropriate segregation of duties so that no single individual controls all phases of a critical process (e.g., requesting, approving, executing, and verifying).',
				code: 'OEC, OM',
				result: 'compliant',
				comment: '§4 explicitly separates initiator, approver, executor, and verifier.',
				ref: {
					section: '§4.2 Segregation of Duties, p.8',
					quote:
						'No single role may both approve a disposal and execute the sale or transfer instructions.'
				},
				confidence: 0.96
			},
			{
				n: 9,
				text: "The policy requires individuals involved in decisions made under it to disclose actual or potential conflicts of interest, in line with Osool's Conflict of Interest Policy.",
				code: 'OEC, OM',
				result: 'compliant',
				comment: '§4.3 references the Conflict of Interest Policy with mandatory disclosure.',
				ref: {
					section: '§4.3, p.9',
					quote:
						'All participants in a disposal decision shall disclose actual or potential conflicts of interest as required by OSOOL-GOV-POL-002.'
				},
				confidence: 0.98
			}
		]
	},
	{
		theme: 'T2',
		id: 'PRP7',
		title: 'Escalation and Approval',
		codes: 'OEC · ISO Cl.5.3',
		intent: 'The policy must state how breaches are escalated and how approvals are obtained.',
		items: [
			{
				n: 1,
				text: 'The escalation path for breaches or non-compliance is explicitly stated.',
				code: 'OEC, ISO',
				result: 'compliant',
				comment: '§9.2 sets a three-tier escalation path with timelines.',
				ref: {
					section: '§9.2 Escalation, p.18',
					quote:
						'Tier 1: Unit Head within 5 business days. Tier 2: Division Head within 10 business days. Tier 3: OE and Internal Audit within 15 business days.'
				},
				confidence: 0.95
			},
			{
				n: 2,
				text: 'Approval and sign-off processes are outlined.',
				code: 'OEC, ISO',
				result: 'compliant',
				comment: 'Approval steps reference the DoA with sign-off responsibilities.',
				ref: {
					section: '§7 Approval Process, p.15',
					quote:
						'All disposals shall be approved in accordance with the Delegation of Authority. Sign-off is recorded in the Disposal Register.'
				},
				confidence: 0.93
			},
			{
				n: 3,
				text: 'The authority to make final decisions on unresolved matters is identified.',
				code: 'OEC, ISO',
				result: 'compliant',
				comment: 'The Board Investment Committee is identified as the final decision authority.',
				ref: {
					section: '§9.3, p.18',
					quote:
						'The Board Investment Committee is the final decision-making authority for any matter unresolved at Tier 3.'
				},
				confidence: 0.97
			}
		]
	},
	{
		theme: 'T2',
		id: 'PRP8',
		title: 'Oversight and Compliance',
		codes: 'OEC · OM',
		intent:
			'The policy must state monitoring mechanisms, list applicable laws, state consequences of non-compliance.',
		items: [
			{
				n: 1,
				text: 'The policy states that monitoring mechanisms are in place.',
				code: 'OEC, ISO',
				result: 'compliant',
				comment: '§9.1 commits to quarterly monitoring with named owners.',
				ref: {
					section: '§9.1 Monitoring, p.17',
					quote:
						'Compliance with this policy shall be monitored quarterly by Internal Audit and reported to the Audit Committee.'
				},
				confidence: 0.96
			},
			{
				n: 2,
				text: 'Applicable laws and regulations are listed.  [H]',
				code: 'OEC, ISO',
				result: 'human',
				comment: 'Legal team must verify completeness of cited regulations.',
				ref: null
			},
			{
				n: 3,
				text: 'Consequences of non-compliance are clearly stated.',
				code: 'OEC, ISO',
				result: 'compliant',
				comment: '§9.4 states disciplinary consequences and reporting to HR.',
				ref: {
					section: '§9.4, p.19',
					quote:
						'Non-compliance may result in disciplinary action up to and including termination, and shall be reported to HR and Internal Audit.'
				},
				confidence: 0.94
			},
			{
				n: 4,
				text: 'The policy commits to a corrective action process for non-compliance.',
				code: 'OEC, ISO',
				result: 'non-compliant',
				comment:
					"Monitoring is described but no formal corrective-action loop is committed. Add a CAPA clause referencing OEC's CAPA process.",
				ref: null,
				confidence: 0.9
			}
		]
	},
	{
		theme: 'T2',
		id: 'PRP10',
		title: 'Policy Need Assessment',
		codes: 'OM',
		intent: 'The basis for establishing or updating this policy must be documented.',
		items: [
			{
				n: 1,
				text: 'The basis for establishing, updating, or retiring this policy is documented.',
				code: 'OM',
				result: 'compliant',
				comment:
					'Version history records the trigger for v1.3 (Vacant Asset Disposal regulation, Q4 2025).',
				ref: {
					section: 'Version History, p.2',
					quote:
						"v1.3 (May 2026): Updated to incorporate new MOMRA regulation on vacant asset disposal and to align with Osool's revised pricing framework."
				},
				confidence: 0.93
			}
		]
	},
	{
		theme: 'T2',
		id: 'PRP11',
		title: 'Measurable Objectives',
		codes: 'ISO Cl.6.2 · OEC',
		intent:
			'Policy objectives must be measurable, have a named responsible party, a target, and a review frequency.',
		items: [
			{
				n: 1,
				text: 'Objectives relevant to this policy are stated.',
				code: 'OEC, ISO',
				result: 'compliant',
				comment: 'Four objectives are listed in §1.2.',
				ref: {
					section: '§1.2 Objectives, p.3',
					quote:
						'(i) maximise realisable value; (ii) ensure transparency; (iii) maintain regulatory compliance; (iv) accelerate disposal of vacant assets.'
				},
				confidence: 0.97
			},
			{
				n: 2,
				text: 'Each objective is measurable and has a defined target.  [H]',
				code: 'OEC, ISO',
				result: 'human',
				comment: 'Measurability and targets require business-context assessment.',
				ref: null
			},
			{
				n: 3,
				text: 'Each objective has a named responsible party.',
				code: 'OEC, ISO',
				result: 'non-compliant',
				comment:
					'Objective (iv) does not name a responsible party. Assign to the Vacant Asset Disposal Unit.',
				ref: {
					section: '§1.2 Objectives, p.3',
					quote:
						'(iv) accelerate disposal of vacant assets — [responsible party not named].'
				},
				confidence: 0.92
			},
			{
				n: 4,
				text: 'Each objective has a target completion date or review frequency.',
				code: 'OEC, ISO',
				result: 'non-compliant',
				comment: 'No completion dates or review cadence stated for any objective.',
				ref: null,
				confidence: 0.93
			},
			{
				n: 5,
				text: 'The policy states that objectives will be monitored and their achievement evaluated.',
				code: 'ISO',
				result: 'compliant',
				comment: '§9.1 commits to monitoring; evaluation is implied by quarterly reporting.',
				ref: {
					section: '§9.1 Monitoring, p.17',
					quote:
						'Compliance and objective achievement shall be reviewed quarterly by Internal Audit.'
				},
				confidence: 0.86
			},
			{
				n: 6,
				text: 'Required resources to achieve objectives are identified.',
				code: 'OEC, ISO',
				result: 'non-compliant',
				comment: 'Resource requirements (headcount, systems, budget) are not specified.',
				ref: null,
				confidence: 0.91
			}
		]
	},
	// ── T3 ──
	{
		theme: 'T3',
		id: 'PRP16',
		title: 'Transparency and Communication',
		codes: 'ISO Cl.7.4 · OEC · OM',
		intent:
			'The policy must define what is communicated, to whom, at what frequency, and through which channels.',
		items: [
			{
				n: 1,
				text: 'The policy defines what information will be communicated, to whom, and at what frequency.',
				code: 'OEC, ISO, OM',
				result: 'compliant',
				comment: '§10.1 specifies the communication matrix.',
				ref: {
					section: '§10.1 Communication, p.19',
					quote:
						'A communication matrix shall identify the audience, content, channel, and frequency for all policy-related communications.'
				},
				confidence: 0.92
			},
			{
				n: 2,
				text: 'Communication channels are defined for both internal and external communications.',
				code: 'OEC, ISO',
				result: 'compliant',
				comment:
					'Internal (Osool intranet, email) and external (Tadawul, MOMRA filings) channels are listed.',
				ref: {
					section: '§10.1, p.19',
					quote:
						'Internal channels: Osool intranet, departmental email. External channels: regulatory filings to MOMRA and disclosures via Tadawul.'
				},
				confidence: 0.94
			},
			{
				n: 3,
				text: "The policy is made readily available to all in-scope employees through Osool's internal electronic channels.",
				code: 'OEC, OM',
				result: 'compliant',
				comment: 'Policy will be published on the Osool Policy Portal upon approval.',
				ref: {
					section: '§10.2, p.20',
					quote:
						'This policy shall be made available to all in-scope employees through the Osool Policy Portal.'
				},
				confidence: 0.96
			},
			{
				n: 4,
				text: 'It is mandatory for employees in scope to be aware of this policy.',
				code: 'OEC, OM',
				result: 'non-compliant',
				comment:
					"Availability is stated but mandatory awareness is not. Add a clause: 'All in-scope employees are required to read and acknowledge this policy.'",
				ref: null,
				confidence: 0.9
			}
		]
	},
	{
		theme: 'T3',
		id: 'PRP18',
		title: 'Training and Awareness',
		codes: 'ISO Cl.7.2, 7.3 · OEC',
		intent:
			'Competency requirements must be stated. Training must be required. Staff must be aware of non-conformance implications.',
		items: [
			{
				n: 1,
				text: 'Competency requirements for roles implementing this policy are stated.',
				code: 'OEC, ISO',
				result: 'non-compliant',
				comment:
					'Roles are named but minimum qualifications or experience levels are not stated.',
				ref: null,
				confidence: 0.92
			},
			{
				n: 2,
				text: 'The policy requires training for all affected staff.',
				code: 'OEC, ISO',
				result: 'compliant',
				comment: '§10.3 mandates annual training delivered by L&D.',
				ref: {
					section: '§10.3 Training, p.20',
					quote:
						'All in-scope staff shall complete annual training on this policy delivered by Learning & Development.'
				},
				confidence: 0.95
			},
			{
				n: 3,
				text: 'New employees are required to be onboarded on this policy.',
				code: 'OEC, ISO',
				result: 'compliant',
				comment: 'Onboarding requirement is referenced in §10.3.',
				ref: {
					section: '§10.3 Training, p.20',
					quote:
						'New hires in scope shall complete this training within 30 days of joining as part of onboarding.'
				},
				confidence: 0.94
			},
			{
				n: 4,
				text: 'The policy states that staff shall be aware of the implications of not conforming to it.',
				code: 'OEC, ISO',
				result: 'compliant',
				comment: '§9.4 sets out consequences of non-conformance.',
				ref: {
					section: '§9.4, p.19',
					quote:
						'Non-compliance may result in disciplinary action up to and including termination.'
				},
				confidence: 0.93
			}
		]
	},
	// ── T4 ──
	{
		theme: 'T4',
		id: 'PRP20',
		title: 'Policy Lifecycle and Review',
		codes: 'ISO Cl.9.3 · OEC · OM',
		intent: 'The policy must state its effective date, version, owner, and review cycle.',
		items: [
			{
				n: 1,
				text: 'The effective date of the policy is stated.',
				code: 'OEC, ISO, OM',
				result: 'compliant',
				comment: 'Cover specifies effective date.',
				ref: { section: 'Cover page', quote: 'Effective Date: 01 June 2026.' },
				confidence: 0.99
			},
			{
				n: 2,
				text: 'A version number and version history are included.',
				code: 'OEC, ISO, OM',
				result: 'compliant',
				comment: 'Version history table present (v1.0 → v1.3).',
				ref: {
					section: 'Version History, p.2',
					quote:
						'v1.0 (Jul 2023), v1.1 (Mar 2024), v1.2 (Nov 2024), v1.3 (May 2026) with change summaries.'
				},
				confidence: 0.98
			},
			{
				n: 3,
				text: 'A named owner for the review process is identified.',
				code: 'OEC, OM',
				result: 'compliant',
				comment: 'Review owner named in §11.',
				ref: {
					section: '§11 Review, p.21',
					quote:
						'The Head of Real Estate Investment Division is responsible for triggering and coordinating reviews.'
				},
				confidence: 0.97
			},
			{
				n: 4,
				text: 'The policy states that it will be updated when regulatory, operational, or strategic conditions change.',
				code: 'OEC, ISO, OM',
				result: 'compliant',
				comment: '§11 commits to ad-hoc updates upon trigger events.',
				ref: {
					section: '§11 Review, p.21',
					quote:
						'This policy shall be reviewed at a minimum every three years, or earlier when regulatory, operational, or strategic conditions change.'
				},
				confidence: 0.96
			},
			{
				n: 5,
				text: 'The policy review cycle is at least once every three years as per the Metapolicy.',
				code: 'OEC, OM',
				result: 'compliant',
				comment: 'Three-year cycle matches Metapolicy.',
				ref: {
					section: '§11 Review, p.21',
					quote: '… reviewed at a minimum every three years …'
				},
				confidence: 0.99
			}
		]
	},
	{
		theme: 'T4',
		id: 'PRP21',
		title: 'Metrics and Performance Measurement',
		codes: 'ISO Cl.9.1 · OEC',
		intent:
			'The policy must define KPIs, monitoring responsibility, reporting frequency, and a feedback loop for improvement.',
		items: [
			{
				n: 1,
				text: 'The policy states that KPIs for measuring its effectiveness are defined.',
				code: 'OEC, ISO',
				result: 'non-compliant',
				comment:
					"§9 mentions 'performance indicators' but does not define them. Recommend at least 3 KPIs: time-to-dispose, value realised vs reserve, audit findings.",
				ref: {
					section: '§9 Monitoring, p.17',
					quote: 'Performance indicators shall be tracked — [KPIs are not enumerated].'
				},
				confidence: 0.91
			},
			{
				n: 2,
				text: 'The frequency of measurement and reporting is stated.',
				code: 'OEC, ISO',
				result: 'compliant',
				comment: 'Quarterly cadence is stated.',
				ref: { section: '§9.1, p.17', quote: 'Reporting frequency: quarterly to the Audit Committee.' },
				confidence: 0.96
			},
			{
				n: 3,
				text: 'Responsibility for monitoring and reporting is assigned.',
				code: 'OEC, ISO',
				result: 'compliant',
				comment: 'Internal Audit is assigned.',
				ref: { section: '§9.1, p.17', quote: 'Internal Audit is responsible for monitoring and reporting.' },
				confidence: 0.95
			},
			{
				n: 4,
				text: 'The policy commits to a feedback loop to inform improvement based on measurement results.',
				code: 'OEC, ISO',
				result: 'non-compliant',
				comment:
					'No formal feedback or continuous-improvement loop. Add a clause linking findings to the policy review process.',
				ref: null,
				confidence: 0.9
			}
		]
	},
	{
		theme: 'T4',
		id: 'PRP22',
		title: 'Benchmarking and Standards',
		codes: 'OEC · OM',
		intent: 'The policy must reference applicable regulatory and industry standards.',
		items: [
			{
				n: 1,
				text: 'The policy identifies applicable industry, regulatory, and international standards or frameworks.  [H]',
				code: 'OEC, ISO',
				result: 'human',
				comment:
					'Benchmarking completeness requires sector expertise — human verification.',
				ref: null
			}
		]
	},
	// ── T5 ──
	{
		theme: 'T5',
		id: 'PRP23',
		title: 'Cross-Functional Areas',
		codes: 'OEC · ISO Cl.8.1',
		intent: 'All in-scope functions must be identified with their roles defined.',
		items: [
			{
				n: 1,
				text: 'All departments and functions in scope are identified.',
				code: 'OEC, ISO',
				result: 'compliant',
				comment: '§4 lists six in-scope functions.',
				ref: {
					section: '§4 Roles & Responsibilities, p.7',
					quote:
						'In scope: Real Estate Investment Division, Asset Disposal Unit, Finance, Legal, Internal Audit, Organizational Excellence.'
				},
				confidence: 0.96
			},
			{
				n: 2,
				text: 'The role and responsibility of each function is defined.',
				code: 'OEC, ISO',
				result: 'compliant',
				comment: 'Each function has explicit RACI assignments.',
				ref: {
					section: '§4 RACI, p.7–8',
					quote:
						'RACI matrix covers Initiation, Valuation, Approval, Execution, Verification, and Reporting.'
				},
				confidence: 0.94
			}
		]
	},
	{
		theme: 'T5',
		id: 'PRP24',
		title: 'Requirements and Stakeholder Communication',
		codes: 'ISO Cl.8.2 · OEC',
		intent:
			'Requirements must be determined, documented, and communicated. Statutory and regulatory requirements must be identified.',
		items: [
			{
				n: 1,
				text: 'The policy states that a process for communicating requirements to stakeholders exists.',
				code: 'ISO',
				result: 'compliant',
				comment: '§10.1 communication matrix covers requirements communication.',
				ref: {
					section: '§10.1, p.19',
					quote:
						'Stakeholders shall be informed of new and changed requirements via the communication matrix.'
				},
				confidence: 0.92
			},
			{
				n: 2,
				text: 'Requirements relevant to this policy are determined and documented.',
				code: 'ISO',
				result: 'compliant',
				comment: '§5 documents disposal requirements (eligibility, pricing, governance).',
				ref: {
					section: '§5 Principles, p.10',
					quote:
						'Requirements covering eligibility, pricing, governance, conflict of interest, and reporting are set out in §5.'
				},
				confidence: 0.93
			},
			{
				n: 3,
				text: 'Statutory and regulatory requirements relevant to this policy are identified.',
				code: 'ISO',
				result: 'non-compliant',
				comment:
					'References mention MOMRA but do not enumerate articles or include Capital Market Authority obligations relevant to disclosure.',
				ref: {
					section: '§11 References, p.21',
					quote:
						'References include MOMRA Vacant Asset Regulation, 2025 — [no specific articles cited; CMA disclosure rules not referenced].'
				},
				confidence: 0.88
			}
		]
	},
	// ── T6 ──
	{
		theme: 'T6',
		id: 'PRP28',
		title: 'Stakeholder Sign-Off and Endorsement',
		codes: 'OEC · ISO Cl.4.2',
		intent: 'A formal approval record must exist at the appropriate authority level.',
		items: [
			{
				n: 1,
				text: 'A formal endorsement or approval record exists at the appropriate authority level per the Delegation of Authority.  [H]',
				code: 'OEC',
				result: 'human',
				comment: 'DoA-level appropriateness must be confirmed by the reviewer.',
				ref: null
			}
		]
	},
	{
		theme: 'T6',
		id: 'PRP29',
		title: 'Interdependency with Other Policies',
		codes: 'OEC · OM',
		intent: 'All referenced policies must be listed in the References section.',
		items: [
			{
				n: 1,
				text: 'All policies this policy depends on or references are listed.',
				code: 'OEC, ISO',
				result: 'compliant',
				comment: '§11 lists all dependent policies with document codes.',
				ref: {
					section: '§11 References, p.21',
					quote:
						'OSOOL-GOV-POL-002 Conflict of Interest; OSOOL-FIN-POL-007 Valuation; OSOOL-GOV-POL-012 Delegation of Authority; OSOOL-RM-POL-009 Records Management.'
				},
				confidence: 0.96
			},
			{
				n: 2,
				text: 'Potential conflicts or overlaps with existing policies have been reviewed.  [H]',
				code: 'OEC',
				result: 'human',
				comment: 'Cross-policy conflict review is a human task.',
				ref: null
			},
			{
				n: 3,
				text: 'Cross-references to related policies are included within the document.',
				code: 'OEC',
				result: 'compliant',
				comment: 'Inline cross-references appear in §4, §6, and §7.',
				ref: {
					section: 'throughout',
					quote:
						'e.g., §4.3 cross-references OSOOL-GOV-POL-002; §7 cross-references OSOOL-GOV-POL-012.'
				},
				confidence: 0.94
			}
		]
	}
];

// ─── Library workspace data (All Policies view) ────────────────────────────

export const FN_META: Record<string, { name: string }> = {
	RE: { name: 'Real Estate' },
	FIN: { name: 'Finance' },
	GOV: { name: 'Governance' },
	HR: { name: 'HR' },
	IT: { name: 'IT' },
	RM: { name: 'Risk' },
	LEG: { name: 'Legal' },
	PROC: { name: 'Procurement' },
	HSE: { name: 'HSE' },
	OPS: { name: 'Operations' }
};

export const STATUS_META: Record<PolicyStatus, { label: string; tone: string }> = {
	approved: { label: 'Approved', tone: 'ok' },
	'in-review': { label: 'In review', tone: 'warn' },
	pending: { label: 'Pending OE', tone: 'info' },
	draft: { label: 'Draft', tone: 'muted' },
	rejected: { label: 'Rejected', tone: 'bad' },
	expiring: { label: 'Expiring', tone: 'warn' },
	overdue: { label: 'Overdue', tone: 'bad' }
};

export const POLICIES: LibraryPolicy[] = [
	// Real Estate
	{ code: 'OSOOL-RE-POL-014', title: 'Digital City Asset Disposal Policy', fn: 'RE', owner: 'Mariam Al-Otaibi', version: '1.3', status: 'in-review', score: 78, pages: 24, nextReview: 'Apr 12, 2027', updatedDays: 2, current: true },
	{ code: 'OSOOL-RE-POL-009', title: 'Ishbilia Compound Valuation', fn: 'RE', owner: 'Saud Al-Mansoori', version: '2.1', status: 'approved', score: 94, pages: 18, nextReview: 'Feb 03, 2029', updatedDays: 107 },
	{ code: 'OSOOL-RE-POL-007', title: 'Land Acquisition & Due Diligence', fn: 'RE', owner: 'Fahd Al-Harbi', version: '1.5', status: 'approved', score: 91, pages: 32, nextReview: 'Oct 21, 2028', updatedDays: 212 },
	{ code: 'OSOOL-RE-POL-011', title: 'Property Lease Management', fn: 'RE', owner: 'Lina Al-Qahtani', version: '3.0', status: 'approved', score: 88, pages: 21, nextReview: 'Jan 14, 2028', updatedDays: 155 },
	{ code: 'OSOOL-RE-POL-018', title: 'Tenant Onboarding & KYC', fn: 'RE', owner: 'Raed Al-Dosari', version: '1.2', status: 'approved', score: 92, pages: 14, nextReview: 'Mar 30, 2028', updatedDays: 78 },
	{ code: 'OSOOL-RE-POL-022', title: 'Real Estate Development Partnership', fn: 'RE', owner: 'Bandar Al-Shehri', version: '2.0', status: 'approved', score: 86, pages: 26, nextReview: 'Sep 04, 2027', updatedDays: 240 },
	{ code: 'OSOOL-RE-POL-005', title: 'Master Plan Approval', fn: 'RE', owner: 'Khalid Al-Faisal', version: '4.1', status: 'approved', score: 95, pages: 30, nextReview: 'Aug 20, 2028', updatedDays: 296 },
	{ code: 'OSOOL-RE-POL-027', title: 'Construction QA & Acceptance', fn: 'RE', owner: 'Tareq Al-Mutairi', version: '0.4', status: 'draft', score: null, pages: 19, nextReview: '—', updatedDays: 5 },
	{ code: 'OSOOL-RE-POL-013', title: 'Pre-development Asset Holding', fn: 'RE', owner: 'Mariam Al-Otaibi', version: '1.1', status: 'expiring', score: 89, pages: 16, nextReview: 'Jul 02, 2026', updatedDays: 680 },
	{ code: 'OSOOL-RE-POL-016', title: 'Real Estate Marketing & Sales', fn: 'RE', owner: 'Sara Al-Rashid', version: '2.2', status: 'approved', score: 90, pages: 22, nextReview: 'Nov 18, 2027', updatedDays: 188 },
	{ code: 'OSOOL-RE-POL-024', title: 'Facilities Management', fn: 'RE', owner: 'Yousef Al-Ghamdi', version: '1.4', status: 'overdue', score: 83, pages: 28, nextReview: 'Feb 11, 2026', updatedDays: 1230 },
	// Finance
	{ code: 'OSOOL-FIN-POL-007', title: 'Valuation & Impairment', fn: 'FIN', owner: 'Hala Al-Zahrani', version: '3.2', status: 'approved', score: 93, pages: 27, nextReview: 'Mar 15, 2028', updatedDays: 120, effectiveDate: '2026-01-15', summary: 'Defines methodologies, frequency, and approval workflow for asset valuation and impairment across Osool. Covers fair-value hierarchy, independent valuer rotation, impairment indicators by asset class, and disclosure requirements aligned with IFRS 13 and IFRS 9. Applies to all balance-sheet assets above the materiality threshold set by Finance.', outline: ['1. Scope & Applicability', '2. Definitions', '3. Valuation Methodologies', '4. Impairment Triggers & Testing', '5. Approval Authority', '6. Disclosure & Reporting', '7. Annexes'], related: ['OSOOL-FIN-POL-011', 'OSOOL-RM-POL-003', 'OSOOL-RE-POL-009'] },
	{ code: 'OSOOL-FIN-POL-002', title: 'Capital Allocation Framework', fn: 'FIN', owner: 'Omar Al-Khalifa', version: '2.0', status: 'in-review', score: 81, pages: 34, nextReview: 'Jun 05, 2027', updatedDays: 9 },
	{ code: 'OSOOL-FIN-POL-004', title: 'Treasury Operations', fn: 'FIN', owner: 'Reema Al-Sabbagh', version: '1.7', status: 'approved', score: 92, pages: 23, nextReview: 'Dec 10, 2027', updatedDays: 175 },
	{ code: 'OSOOL-FIN-POL-011', title: 'Financial Reporting (IFRS)', fn: 'FIN', owner: 'Hala Al-Zahrani', version: '4.0', status: 'approved', score: 96, pages: 42, nextReview: 'Jul 22, 2028', updatedDays: 265 },
	{ code: 'OSOOL-FIN-POL-013', title: 'Hedging & Derivatives', fn: 'FIN', owner: 'Reema Al-Sabbagh', version: '1.2', status: 'approved', score: 89, pages: 20, nextReview: 'Apr 09, 2028', updatedDays: 142 },
	{ code: 'OSOOL-FIN-POL-006', title: 'Budgeting & Forecasting', fn: 'FIN', owner: 'Ali Al-Otaibi', version: '2.3', status: 'approved', score: 90, pages: 18, nextReview: 'Aug 01, 2027', updatedDays: 198 },
	{ code: 'OSOOL-FIN-POL-019', title: 'Tax Compliance', fn: 'FIN', owner: 'Nada Al-Buraidi', version: '1.1', status: 'approved', score: 88, pages: 16, nextReview: 'Oct 30, 2027', updatedDays: 222 },
	{ code: 'OSOOL-FIN-POL-015', title: 'Accounts Receivable & Credit', fn: 'FIN', owner: 'Ali Al-Otaibi', version: '0.6', status: 'draft', score: null, pages: 12, nextReview: '—', updatedDays: 11 },
	// Governance
	{ code: 'OSOOL-GOV-POL-002', title: 'Conflict of Interest', fn: 'GOV', owner: 'Faisal Al-Jubeir', version: '3.1', status: 'approved', score: 97, pages: 14, nextReview: 'Jan 28, 2029', updatedDays: 90 },
	{ code: 'OSOOL-GOV-POL-012', title: 'Delegation of Authority', fn: 'GOV', owner: 'Faisal Al-Jubeir', version: '5.0', status: 'approved', score: 95, pages: 38, nextReview: 'May 15, 2029', updatedDays: 5 },
	{ code: 'OSOOL-GOV-POL-004', title: 'Whistleblowing & Speak-Up', fn: 'GOV', owner: 'Amal Al-Hashimi', version: '2.2', status: 'approved', score: 93, pages: 11, nextReview: 'Sep 12, 2028', updatedDays: 250 },
	{ code: 'OSOOL-GOV-POL-001', title: 'Board Charter', fn: 'GOV', owner: 'Faisal Al-Jubeir', version: '6.0', status: 'approved', score: 94, pages: 28, nextReview: 'Dec 05, 2028', updatedDays: 165 },
	{ code: 'OSOOL-GOV-POL-006', title: 'Code of Conduct', fn: 'GOV', owner: 'Amal Al-Hashimi', version: '4.0', status: 'approved', score: 92, pages: 24, nextReview: 'Feb 27, 2028', updatedDays: 80 },
	{ code: 'OSOOL-GOV-POL-008', title: 'Anti-Bribery & Corruption', fn: 'GOV', owner: 'Amal Al-Hashimi', version: '2.0', status: 'approved', score: 91, pages: 16, nextReview: 'Jun 18, 2028', updatedDays: 130 },
	{ code: 'OSOOL-GOV-POL-014', title: 'Related Party Transactions', fn: 'GOV', owner: 'Faisal Al-Jubeir', version: '1.0', status: 'pending', score: 88, pages: 19, nextReview: 'Jul 04, 2029', updatedDays: 6 },
	// HR
	{ code: 'OSOOL-HR-POL-003', title: 'Recruitment & Onboarding', fn: 'HR', owner: 'Noura Al-Saqer', version: '3.4', status: 'approved', score: 90, pages: 22, nextReview: 'Apr 19, 2028', updatedDays: 144, effectiveDate: '2025-12-01', summary: 'Governs the end-to-end recruitment lifecycle from requisition to first-90-days onboarding. Covers job-grade requirements, sourcing channels (including Saudi-national priority via Nitaqat), interview panel composition, offer authority by grade, and the mandatory onboarding curriculum. Aligns with Saudi Labor Law and Osool\'s Saudization commitments.', outline: ['1. Scope & Applicability', '2. Requisition & Approval', '3. Sourcing & Saudi-National Priority', '4. Selection & Interview Panels', '5. Offer & Letter of Engagement', '6. Onboarding (Days 0–90)', '7. Probation & Confirmation'], related: ['OSOOL-HR-POL-011', 'OSOOL-HR-POL-008', 'OSOOL-HR-POL-005'] },
	{ code: 'OSOOL-HR-POL-008', title: 'Performance Management', fn: 'HR', owner: 'Noura Al-Saqer', version: '2.1', status: 'approved', score: 89, pages: 18, nextReview: 'Nov 02, 2027', updatedDays: 206 },
	{ code: 'OSOOL-HR-POL-005', title: 'Compensation & Benefits', fn: 'HR', owner: 'Mohammed Al-Aqeel', version: '4.2', status: 'in-review', score: 84, pages: 26, nextReview: 'Jun 25, 2028', updatedDays: 8 },
	{ code: 'OSOOL-HR-POL-011', title: 'Saudization & Localization (Nitaqat)', fn: 'HR', owner: 'Noura Al-Saqer', version: '1.8', status: 'approved', score: 96, pages: 14, nextReview: 'Jan 09, 2028', updatedDays: 118 },
	{ code: 'OSOOL-HR-POL-002', title: 'Leave & Attendance', fn: 'HR', owner: 'Mohammed Al-Aqeel', version: '2.5', status: 'expiring', score: 86, pages: 12, nextReview: 'Aug 05, 2026', updatedDays: 720 },
	{ code: 'OSOOL-HR-POL-009', title: 'Disciplinary Action', fn: 'HR', owner: 'Noura Al-Saqer', version: '1.3', status: 'approved', score: 87, pages: 15, nextReview: 'Mar 11, 2028', updatedDays: 170 },
	// IT
	{ code: 'OSOOL-IT-POL-001', title: 'Information Security (ISMS)', fn: 'IT', owner: 'Hisham Al-Rajhi', version: '3.0', status: 'approved', score: 94, pages: 46, nextReview: 'Oct 14, 2028', updatedDays: 60 },
	{ code: 'OSOOL-IT-POL-003', title: 'Acceptable Use', fn: 'IT', owner: 'Hisham Al-Rajhi', version: '2.4', status: 'approved', score: 88, pages: 10, nextReview: 'May 03, 2028', updatedDays: 182, effectiveDate: '2025-11-20', summary: 'Sets out what employees may and may not do with Osool-issued devices, accounts, and network access. Covers personal use, prohibited categories (gambling, illegal content, third-party generative AI for confidential data), removable media, and remote-work obligations. Read together with the Information Security and Data Classification policies.', outline: ['1. Scope', '2. Acceptable Personal Use', '3. Prohibited Activities', '4. Removable Media & External Services', '5. Remote Work & BYOD', '6. Enforcement & Disciplinary Action'], related: ['OSOOL-IT-POL-001', 'OSOOL-IT-POL-007', 'OSOOL-GOV-POL-006'] },
	{ code: 'OSOOL-IT-POL-005', title: 'Cloud Services Adoption', fn: 'IT', owner: 'Dalia Al-Ameri', version: '1.0', status: 'in-review', score: 79, pages: 24, nextReview: 'Sep 30, 2028', updatedDays: 11 },
	{ code: 'OSOOL-IT-POL-007', title: 'IT Disaster Recovery', fn: 'IT', owner: 'Dalia Al-Ameri', version: '2.2', status: 'approved', score: 91, pages: 30, nextReview: 'Feb 18, 2028', updatedDays: 96 },
	{ code: 'OSOOL-IT-POL-009', title: 'Third-Party IT Risk', fn: 'IT', owner: 'Hisham Al-Rajhi', version: '0.7', status: 'draft', score: null, pages: 17, nextReview: '—', updatedDays: 3 },
	// Risk
	{ code: 'OSOOL-RM-POL-001', title: 'Enterprise Risk Management', fn: 'RM', owner: 'Tareq Al-Mutairi', version: '3.3', status: 'approved', score: 93, pages: 32, nextReview: 'Dec 22, 2028', updatedDays: 140, effectiveDate: '2025-08-01', summary: 'Establishes the integrated framework for identifying, assessing, treating, and monitoring risks across Osool. Defines the three lines of defence model, the enterprise risk taxonomy (strategic, financial, operational, regulatory, ESG), risk appetite statements approved by the Board, and escalation paths. Outputs feed quarterly Audit Committee reporting.', outline: ['1. Purpose & Scope', '2. Risk Taxonomy', '3. Three Lines of Defence', '4. Risk Appetite & Tolerances', '5. Identification & Assessment', '6. Treatment & Monitoring', '7. Reporting & Escalation', '8. Annexes'], related: ['OSOOL-RM-POL-003', 'OSOOL-RM-POL-005', 'OSOOL-GOV-POL-004'] },
	{ code: 'OSOOL-RM-POL-003', title: 'Investment Risk', fn: 'RM', owner: 'Omar Al-Khalifa', version: '2.1', status: 'approved', score: 90, pages: 25, nextReview: 'Jul 30, 2028', updatedDays: 200 },
	{ code: 'OSOOL-RM-POL-005', title: 'Business Continuity', fn: 'RM', owner: 'Tareq Al-Mutairi', version: '1.5', status: 'expiring', score: 88, pages: 28, nextReview: 'Jul 28, 2026', updatedDays: 700 },
	{ code: 'OSOOL-RM-POL-007', title: 'Crisis Management', fn: 'RM', owner: 'Tareq Al-Mutairi', version: '1.2', status: 'approved', score: 86, pages: 20, nextReview: 'Mar 02, 2028', updatedDays: 160 },
	// Legal
	{ code: 'OSOOL-LEG-POL-001', title: 'Contract Management', fn: 'LEG', owner: 'Rana Al-Sudairy', version: '2.6', status: 'approved', score: 92, pages: 22, nextReview: 'Aug 14, 2027', updatedDays: 230 },
	{ code: 'OSOOL-LEG-POL-003', title: 'Litigation Management', fn: 'LEG', owner: 'Rana Al-Sudairy', version: '1.4', status: 'approved', score: 89, pages: 18, nextReview: 'Feb 09, 2028', updatedDays: 104 },
	{ code: 'OSOOL-LEG-POL-005', title: 'IP & Brand Protection', fn: 'LEG', owner: 'Rana Al-Sudairy', version: '0.5', status: 'draft', score: null, pages: 14, nextReview: '—', updatedDays: 14 },
	// Procurement
	{ code: 'OSOOL-PROC-POL-002', title: 'Vendor Onboarding', fn: 'PROC', owner: 'Yousef Al-Ghamdi', version: '1.0', status: 'rejected', score: 62, pages: 18, nextReview: '—', updatedDays: 24 },
	{ code: 'OSOOL-PROC-POL-004', title: 'Tendering & Bidding', fn: 'PROC', owner: 'Bandar Al-Shehri', version: '2.3', status: 'approved', score: 91, pages: 24, nextReview: 'Nov 27, 2027', updatedDays: 185 },
	{ code: 'OSOOL-PROC-POL-006', title: 'Local Content (Etimad)', fn: 'PROC', owner: 'Yousef Al-Ghamdi', version: '1.2', status: 'approved', score: 89, pages: 16, nextReview: 'May 06, 2028', updatedDays: 148 },
	// HSE
	{ code: 'OSOOL-HSE-POL-001', title: 'Workplace Safety', fn: 'HSE', owner: 'Ibrahim Al-Hazmi', version: '2.1', status: 'approved', score: 94, pages: 20, nextReview: 'Apr 30, 2028', updatedDays: 158 },
	{ code: 'OSOOL-HSE-POL-003', title: 'Environmental Compliance', fn: 'HSE', owner: 'Ibrahim Al-Hazmi', version: '1.3', status: 'approved', score: 88, pages: 18, nextReview: 'Oct 03, 2027', updatedDays: 215 },
	// Operations
	{ code: 'OSOOL-OPS-POL-001', title: 'Records Management', fn: 'OPS', owner: 'Layla Al-Shahrani', version: '2.0', status: 'approved', score: 93, pages: 22, nextReview: 'Jan 16, 2028', updatedDays: 112 },
	{ code: 'OSOOL-OPS-POL-003', title: 'Travel & Expense', fn: 'OPS', owner: 'Layla Al-Shahrani', version: '1.8', status: 'overdue', score: 81, pages: 14, nextReview: 'Mar 11, 2026', updatedDays: 1090 }
];

export const STATUS_DIST: Array<{ id: PolicyStatus | 'draft'; label: string; count: number; tone: string }> = [
	{ id: 'approved', label: 'Approved', count: 102, tone: 'ok' },
	{ id: 'in-review', label: 'In review', count: 7, tone: 'warn' },
	{ id: 'pending', label: 'Pending OE', count: 3, tone: 'info' },
	{ id: 'draft', label: 'Drafts', count: 14, tone: 'muted' },
	{ id: 'expiring', label: 'Expiring', count: 12, tone: 'warn' },
	{ id: 'overdue', label: 'Overdue', count: 4, tone: 'bad' }
];

export const TOTAL_COUNT = STATUS_DIST.reduce((a, s) => a + s.count, 0); // 142

export const FN_DIST: Array<{ id: string; count: number; avg: number }> = [
	{ id: 'RE', count: 34, avg: 88 },
	{ id: 'FIN', count: 21, avg: 91 },
	{ id: 'GOV', count: 18, avg: 93 },
	{ id: 'HR', count: 15, avg: 89 },
	{ id: 'IT', count: 14, avg: 88 },
	{ id: 'RM', count: 11, avg: 89 },
	{ id: 'LEG', count: 9, avg: 88 },
	{ id: 'PROC', count: 8, avg: 84 },
	{ id: 'HSE', count: 7, avg: 91 },
	{ id: 'OPS', count: 5, avg: 87 }
];

export const TODAY = new Date('2026-05-20');
