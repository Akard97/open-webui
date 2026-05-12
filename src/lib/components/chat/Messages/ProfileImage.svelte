<script lang="ts">
	import { WEBUI_BASE_URL } from '$lib/constants';
	import { safeImageUrl } from '$lib/utils/safeImageUrl';

	export let className = 'size-8';
	export let rounded = true;
	export let src = `${WEBUI_BASE_URL}/static/favicon.png`;

	// Model-profile-image URLs support a `theme=dark` query param that the
	// backend uses to swap to a `-dark` static sibling. For those URLs we
	// render two <img>s and let CSS pick based on the active theme.
	$: isModelProfileImage = typeof src === 'string' && src.includes('/models/model/profile/image');
	$: darkSrc = isModelProfileImage
		? `${src}${src.includes('?') ? '&' : '?'}theme=dark`
		: null;
</script>

{#if darkSrc}
	<img
		aria-hidden="true"
		src={safeImageUrl(src)}
		class=" {className} object-cover {rounded ? 'rounded-full' : ''} block dark:hidden"
		alt="profile"
		draggable="false"
	/>
	<img
		aria-hidden="true"
		src={safeImageUrl(darkSrc)}
		class=" {className} object-cover {rounded ? 'rounded-full' : ''} hidden dark:block"
		alt="profile"
		draggable="false"
	/>
{:else}
	<img
		aria-hidden="true"
		src={safeImageUrl(src)}
		class=" {className} object-cover {rounded ? 'rounded-full' : ''}"
		alt="profile"
		draggable="false"
	/>
{/if}
