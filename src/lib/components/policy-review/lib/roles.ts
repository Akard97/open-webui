// Derives the identity subtitle shown in the Policy Review sidebar footer.
// OE members (approvers/reviewers) are labelled with their Organizational
// Excellence role; everyone else is a plain library viewer. Pure function so
// the branching is unit-tested and the component template stays declarative.

export function policyRoleLabel(canApprove: boolean, canUseChecker: boolean): string {
	if (canApprove) return 'Organizational Excellence · Approver';
	if (canUseChecker) return 'Organizational Excellence · Reviewer';
	return 'Viewer';
}
