<script lang="ts">
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	const versions = [
		{
			v: 'v3',
			current: true,
			when: '2 days ago',
			what: 'Replaced 3 files · index.html, charts.css, logo.svg'
		},
		{ v: 'v2', current: false, when: '1 week ago', what: 'Replaced 1 file · index.html' },
		{ v: 'v1', current: false, when: 'Aug 12, 2026', what: 'First publish · 3 files' }
	];
</script>

<div class="st-pane flex flex-col gap-2.5">
	<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-1.5">
		{#each versions as ver (ver.v)}
			<div class="flex gap-3.5 border-b border-[var(--st-hairline)] px-1 py-3.5 last:border-b-0">
				<span
					class="mt-1.5 h-2.5 w-2.5 flex-none rounded-full {ver.current
						? 'bg-[var(--st-live)] ring-4 ring-[var(--st-live-soft)]'
						: 'bg-[var(--st-faint)]'}"
				></span>
				<div class="min-w-0 flex-1">
					<div class="flex items-center gap-2 text-[13.5px] font-semibold">
						{ver.v}
						{#if ver.current}
							<span
								class="rounded-full bg-[var(--st-live-soft)] px-1.5 py-0.5 text-[10px] font-bold tracking-[0.05em] text-[var(--st-live)]"
								>{$i18n.t('CURRENT')}</span
							>
						{/if}
						<span class="text-xs font-normal text-[var(--st-faint)]">· {ver.when}</span>
					</div>
					<div class="text-xs text-[var(--st-muted)]">{ver.what}</div>
				</div>
				{#if !ver.current}
					<button type="button" class="st-btn self-center" disabled title={$i18n.t('Coming soon')}
						>{$i18n.t('Restore')}</button
					>
				{/if}
			</div>
		{/each}
	</div>
	<p class="text-xs text-[var(--st-faint)]">
		{$i18n.t('Sample data — this ships in a later phase.')}
	</p>
</div>
