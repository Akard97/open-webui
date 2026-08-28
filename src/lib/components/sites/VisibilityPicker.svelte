<script lang="ts">
	import { getContext } from 'svelte';
	import AccessControl from '$lib/components/workspace/common/AccessControl.svelte';

	const i18n = getContext('i18n');

	let { level = $bindable('private'), accessGrants = $bindable([]) } = $props();

	const options = $derived([
		{ value: 'private', title: $i18n.t('Only me'), sub: $i18n.t('Private link — just for you') },
		{
			value: 'specific',
			title: $i18n.t('Specific people or groups'),
			sub: $i18n.t('Pick who can open the link')
		},
		{
			value: 'internal',
			title: $i18n.t('Everyone with an account'),
			sub: $i18n.t('Anyone signed in')
		},
		{
			value: 'public',
			title: $i18n.t('Public — no login needed'),
			sub: $i18n.t('Anyone with the link')
		}
	]);
</script>

<div class="flex max-w-md flex-col gap-1.5" role="radiogroup" aria-label={$i18n.t('Who can view')}>
	{#each options as o (o.value)}
		<label
			class="flex cursor-pointer items-center gap-2.5 rounded-[10px] border px-3 py-2.5 text-[13.5px] transition-colors duration-150
				{level === o.value
				? 'border-[var(--st-accent)] bg-[var(--st-accent-soft)]'
				: 'border-[var(--st-hairline)]'}"
		>
			<input type="radio" name="site-level" value={o.value} bind:group={level} />
			<span>
				{o.title}
				<span class="block text-[11.5px] text-[var(--st-muted)]">{o.sub}</span>
			</span>
		</label>
	{/each}
</div>
{#if level === 'specific'}
	<div class="mt-2 max-w-md">
		<AccessControl
			bind:accessGrants
			accessRoles={['read']}
			sharePublic={false}
			showVisibilitySelect={false}
		/>
	</div>
{/if}
