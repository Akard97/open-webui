<script lang="ts">
	const ROLES = [
		{ perm: 'policy_checker', name: 'Policy Checker (Reviewer)', desc: 'Upload, scan, review, and submit policies for approval.' },
		{ perm: 'policy_approver', name: 'Policy Approver', desc: 'Approve & publish or reject submitted reviews.' },
		{ perm: 'policy_admin', name: 'Policy Admin', desc: 'Manage this checklist, scoring, and standards.' }
	];
</script>

<div class="ax">
	<p class="ax-help">
		Access to the Policy Review tool is controlled by three group permissions. The policy
		library is open to everyone; the surfaces below are granted per group in the Admin Panel.
	</p>
	<div class="ax-cards">
		{#each ROLES as r (r.perm)}
			<div class="ax-card">
				<div class="ax-name">{r.name}</div>
				<code class="ax-perm">features.{r.perm}</code>
				<div class="ax-desc">{r.desc}</div>
			</div>
		{/each}
	</div>
	<a class="ax-link" href="/admin/users/groups">
		Manage groups &amp; permissions in the Admin Panel →
	</a>
	<p class="ax-note">System administrators always have all three.</p>
</div>

<style>
	.ax { display: grid; gap: 14px; }
	.ax-help { font-size: 12.5px; color: var(--ink-500); max-width: 70ch; }
	.ax-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
	.ax-card { border: 1px solid var(--ink-100); border-radius: 11px; padding: 13px 15px; }
	.ax-name { font-size: 13px; font-weight: 600; }
	.ax-perm { font-size: 11px; font-family: var(--mono); color: var(--primary); background: var(--primary-50); padding: 2px 6px; border-radius: 5px; display: inline-block; margin: 5px 0; }
	.ax-desc { font-size: 12px; color: var(--ink-600); }
	.ax-link { font-size: 13px; color: var(--primary); text-decoration: none; }
	.ax-note { font-size: 12px; color: var(--ink-400); }
</style>
