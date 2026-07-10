<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	import { generateAvatar, getAvatarQuota } from '$lib/apis/avatar';
	import { generateInitialsImage } from '$lib/utils';
	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { isReusablePhoto, dataUrlToBlob } from './aiAvatar';

	const i18n = getContext<any>('i18n');
	const dispatch = createEventDispatcher();

	export let show = false;
	export let currentImage = '';
	export let user: { name?: string; email?: string } | null = null;

	let photoInputElement: HTMLInputElement;
	let sourceDataUrl = '';
	let resultDataUrl = '';
	let generating = false;
	let remaining: number | null = null;
	let limit: number | null = null;

	$: initialsImage = user?.name ? generateInitialsImage(user.name) : '';
	$: canUseCurrent = isReusablePhoto(currentImage, initialsImage);

	let wasShown = false;
	$: if (show && !wasShown) {
		wasShown = true;
		init();
	} else if (!show && wasShown) {
		wasShown = false;
		sourceDataUrl = '';
		resultDataUrl = '';
		generating = false;
	}

	const init = async () => {
		try {
			const quota = await getAvatarQuota(localStorage.token);
			remaining = quota.remaining;
			limit = quota.limit;
		} catch (err) {
			toast.error(`${err}`);
		}
	};

	const onPhotoSelected = () => {
		const file = photoInputElement.files?.[0];
		if (!file) {
			return;
		}
		photoInputElement.value = '';
		if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
			toast.error($i18n.t('Unsupported image type. Use PNG, JPEG or WebP.'));
			return;
		}
		const reader = new FileReader();
		reader.onload = (event) => {
			sourceDataUrl = `${event.target?.result ?? ''}`;
			resultDataUrl = '';
		};
		reader.readAsDataURL(file);
	};

	const generate = async () => {
		if (!sourceDataUrl || generating) {
			return;
		}
		generating = true;
		try {
			const res = await generateAvatar(localStorage.token, dataUrlToBlob(sourceDataUrl));
			resultDataUrl = res.image;
			remaining = res.remaining;
		} catch (err) {
			toast.error(`${err}`);
		} finally {
			generating = false;
		}
	};

	// Shrink the 1024px result to <=512px webp so the stored profile_image_url stays small.
	const resizeResult = (src: string): Promise<string> =>
		new Promise((resolve) => {
			const img = new Image();
			img.onload = () => {
				const canvas = document.createElement('canvas');
				const edge = Math.min(512, img.width);
				canvas.width = edge;
				canvas.height = edge;
				canvas.getContext('2d')?.drawImage(img, 0, 0, edge, edge);
				resolve(canvas.toDataURL('image/webp', 0.85));
			};
			img.onerror = () => resolve(src);
			img.src = src;
		});

	const apply = async () => {
		dispatch('apply', await resizeResult(resultDataUrl));
		show = false;
	};
</script>

<input
	bind:this={photoInputElement}
	type="file"
	hidden
	accept="image/png,image/jpeg,image/webp"
	on:change={onPhotoSelected}
/>

<Modal bind:show size="sm">
	<div class="px-5 pt-4 pb-5">
		<div class="flex justify-between items-center dark:text-gray-300">
			<div class="text-lg font-medium self-center">{$i18n.t('AI Avatar')}</div>
			<button
				class="self-center"
				type="button"
				aria-label={$i18n.t('Close')}
				on:click={() => {
					show = false;
				}}
			>
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
					<path
						d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z"
					/>
				</svg>
			</button>
		</div>

		<div class="text-xs text-gray-500 mt-1">
			{$i18n.t('Create a stylized professional avatar from a photo.')}
		</div>

		<div class="flex justify-center gap-6 my-5">
			<div class="flex flex-col items-center gap-2">
				<button
					type="button"
					class="size-24 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden flex items-center justify-center border border-dashed border-gray-300 dark:border-gray-600"
					on:click={() => photoInputElement.click()}
					aria-label={$i18n.t('Upload a photo')}
				>
					{#if sourceDataUrl}
						<img src={sourceDataUrl} alt="" class="size-24 object-cover" />
					{:else}
						<span class="text-xs text-gray-500 px-2 text-center">{$i18n.t('Upload a photo')}</span>
					{/if}
				</button>
				{#if canUseCurrent && sourceDataUrl !== currentImage}
					<button
						type="button"
						class="text-xs text-gray-500 hover:text-gray-800 dark:hover:text-gray-300"
						on:click={() => {
							sourceDataUrl = currentImage;
							resultDataUrl = '';
						}}>{$i18n.t('Use current photo')}</button
					>
				{/if}
			</div>

			<div class="flex flex-col items-center gap-2">
				<div
					class="size-24 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden flex items-center justify-center"
				>
					{#if generating}
						<Spinner className="size-5" />
					{:else if resultDataUrl}
						<img src={resultDataUrl} alt="" class="size-24 object-cover" />
					{:else}
						<span class="text-xs text-gray-400 px-2 text-center">{$i18n.t('Preview')}</span>
					{/if}
				</div>
			</div>
		</div>

		<div class="text-xs text-gray-500 mb-4">
			{$i18n.t('Your photo is sent to OpenAI to create the avatar. It is not stored.')}
			{#if remaining !== null && limit !== null}
				&middot; {remaining}/{limit} {$i18n.t('generations left today')}
			{/if}
		</div>

		<div class="flex justify-end gap-2">
			<button
				class="px-3.5 py-1.5 text-sm font-medium rounded-full bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition disabled:opacity-50"
				type="button"
				disabled={!sourceDataUrl || generating || remaining === 0}
				on:click={generate}
			>
				{resultDataUrl ? $i18n.t('Regenerate') : $i18n.t('Generate')}
			</button>
			{#if resultDataUrl && !generating}
				<button
					class="px-3.5 py-1.5 text-sm font-medium rounded-full bg-emerald-700 hover:bg-emerald-800 text-white transition"
					type="button"
					on:click={apply}
				>
					{$i18n.t('Use avatar')}
				</button>
			{/if}
		</div>
	</div>
</Modal>
