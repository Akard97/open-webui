<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import * as api from '../lib/api';
	import {
		openModal, token, loadBootstrap
	} from '../lib/store';

	let name = '';
	let key = '';
	let visibility: 'team' | 'restricted' = 'team';
	let busy = false;
	let err = '';

	// ModalHost owns only the create flows; settings kinds are rendered by the
	// dedicated dialogs in chrome/access/ and must not open this overlay too.
	$: req =
		$openModal &&
		($openModal.kind === 'team' || $openModal.kind === 'workspace' || $openModal.kind === 'workstream')
			? $openModal
			: null;
	$: if (req) reset(req);

	async function reset(r: NonNullable<typeof req>) {
		name = '';
		key = '';
		visibility = 'team';
		err = '';
	}

	function close() {
		openModal.set(null);
	}

	async function submit() {
		if (!req) return;
		busy = true;
		err = '';
		try {
			if (req.kind === 'team') {
				await api.createTeam(token(), { name, key: key.toUpperCase() });
			} else if (req.kind === 'workspace') {
				await api.createWorkspace(token(), req.teamId, { name, visibility });
			} else if (req.kind === 'workstream') {
				await api.createWorkstream(token(), req.workspaceId, { name });
			}
			await loadBootstrap();
			close();
		} catch (e: any) {
			err = typeof e === 'string' ? e : (e?.detail ?? 'Something went wrong.');
		} finally {
			busy = false;
		}
	}

	const TITLES = { team: 'New team', workspace: 'New workspace', workstream: 'New workstream' };
</script>

{#if req}
	<div class="fixed inset-0 z-50 flex items-center justify-center">
		<div class="absolute inset-0 bg-black/40" onclick={close} role="presentation"></div>
		<div class="relative w-[420px] max-w-[92%] rounded-xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 shadow-2xl p-5">
			<div class="flex items-center mb-4">
				<h2 class="text-base font-semibold flex-1">{TITLES[req.kind]}</h2>
				<button class="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-900" onclick={close}><Icon name="x" size={16} /></button>
			</div>

			{#if err}<div class="mb-3 text-sm text-red-600">{err}</div>{/if}

			<div class="space-y-3">
				<input class="w-full text-sm px-3 py-2 rounded border border-gray-300 dark:border-gray-700 bg-transparent" placeholder="Name" bind:value={name} autofocus />
				{#if req.kind === 'team'}
					<input class="w-full text-sm px-3 py-2 rounded border border-gray-300 dark:border-gray-700 bg-transparent font-mono uppercase" placeholder="Key (e.g. OSL)" bind:value={key} maxlength="6" />
					<p class="text-xs text-gray-400">The key prefixes task numbers, e.g. {(key || 'OSL').toUpperCase()}-1.</p>
				{:else if req.kind === 'workspace'}
					<select class="w-full text-sm px-3 py-2 rounded border border-gray-300 dark:border-gray-700 bg-transparent" bind:value={visibility}>
						<option value="team">Visible to whole team</option>
						<option value="restricted">Restricted to members</option>
					</select>
				{/if}
			</div>
			<div class="flex justify-end gap-2 mt-5">
				<button class="text-sm px-3 py-1.5 rounded border border-gray-300 dark:border-gray-700" onclick={close}>Cancel</button>
				<button class="text-sm px-3 py-1.5 rounded bg-primary text-primary-foreground disabled:opacity-50" disabled={busy || !name.trim() || (req.kind === 'team' && !key.trim())} onclick={submit}>Create</button>
			</div>
		</div>
	</div>
{/if}
