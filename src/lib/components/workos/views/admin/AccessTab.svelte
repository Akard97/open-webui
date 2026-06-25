<script lang="ts">
	const ROLES = [
		{ perm: 'workos', name: 'WorkOS user', desc: 'Use the WorkOS tool; see and act within teams you belong to.' },
		{ perm: 'workos_admin', name: 'WorkOS admin', desc: 'Open this admin center; oversee all teams and global rules.' }
	];
</script>

<div class="space-y-4">
	<p class="text-sm text-gray-500 max-w-prose">
		Access is controlled by two group permissions, granted per group in the Admin Panel.
		Membership within WorkOS (team/workspace roles) is managed inside each team.
	</p>
	<div class="grid gap-3" style="grid-template-columns: repeat(auto-fit, minmax(220px, 1fr))">
		{#each ROLES as r (r.perm)}
			<div class="border border-gray-200 dark:border-gray-800 rounded-lg p-3.5">
				<div class="text-sm font-semibold">{r.name}</div>
				<code class="text-[11px] text-primary bg-accent px-1.5 py-0.5 rounded inline-block my-1.5">features.{r.perm}</code>
				<div class="text-xs text-gray-500">{r.desc}</div>
			</div>
		{/each}
	</div>
	<a class="text-sm text-primary" href="/admin/users/groups">Manage groups &amp; permissions in the Admin Panel →</a>
	<p class="text-xs text-gray-400">System administrators always have both.</p>
</div>
