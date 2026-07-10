<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog';
	import * as Select from '$lib/components/ui/select';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
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
	const VISIBILITY_LABEL: Record<string, string> = {
		team: 'Visible to whole team',
		restricted: 'Restricted to members'
	};
</script>

<Dialog.Root open={req != null} onOpenChange={(o) => { if (!o) close(); }}>
	<Dialog.Content class="sm:max-w-md rounded-2xl">
		<Dialog.Header>
			<Dialog.Title>{req ? TITLES[req.kind] : ''}</Dialog.Title>
			<Dialog.Description class="sr-only">{req ? `Enter a name to create a new ${req.kind}.` : ''}</Dialog.Description>
		</Dialog.Header>

		{#if err}<div class="text-sm text-red-600">{err}</div>{/if}

		<div class="space-y-3">
			<Input placeholder="Name" bind:value={name} autofocus />
			{#if req?.kind === 'team'}
				<Input class="font-mono uppercase" placeholder="Key (e.g. OSL)" bind:value={key} maxlength={6} />
				<p class="text-xs text-gray-400">The key prefixes task numbers, e.g. {(key || 'OSL').toUpperCase()}-1.</p>
			{:else if req?.kind === 'workspace'}
				<Select.Root type="single" bind:value={visibility}>
					<Select.Trigger class="w-full">{VISIBILITY_LABEL[visibility]}</Select.Trigger>
					<Select.Content>
						<Select.Item value="team" label="Visible to whole team" />
						<Select.Item value="restricted" label="Restricted to members" />
					</Select.Content>
				</Select.Root>
			{/if}
		</div>

		<Dialog.Footer>
			<Button variant="outline" size="sm" onclick={close}>Cancel</Button>
			<Button size="sm" onclick={submit} disabled={busy || !name.trim() || (req?.kind === 'team' && !key.trim())}>Create</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
