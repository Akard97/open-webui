<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { config } from '$lib/stores';
	import { injectCsp } from '$lib/utils/csp';
	import { parseHeightHint, WIDGET_HEIGHT_MESSAGE } from '$lib/utils/widgets';

	export let id: string;
	export let html: string = '';

	// Strict default: no network, no navigation; inline script/style only.
	const DEFAULT_CSP =
		"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: https:; font-src data: https:";

	const MIN_HEIGHT = 80;
	const MAX_HEIGHT = 640;

	let iframeEl: HTMLIFrameElement | null = null;
	let height = 320;
	let fixedHeight = false;

	// Reports the document height to the parent; contentWindow is unreachable
	// from outside because the sandboxed srcdoc has an opaque origin.
	const HEIGHT_REPORTER = `<script>(function(){var send=function(){try{parent.postMessage({type:'${WIDGET_HEIGHT_MESSAGE}',height:document.documentElement.scrollHeight},'*');}catch(e){}};if(window.ResizeObserver){new ResizeObserver(send).observe(document.documentElement);}window.addEventListener('load',send);send();})();<\/script>`;

	$: {
		const hint = parseHeightHint(html);
		if (hint !== null) {
			height = hint;
			fixedHeight = true;
		}
	}

	$: srcdoc = injectCsp(html, $config?.ui?.iframe_csp || DEFAULT_CSP) + HEIGHT_REPORTER;

	const onMessage = (event: MessageEvent) => {
		if (fixedHeight) return;
		if (!iframeEl || event.source !== iframeEl.contentWindow) return;
		if (event.data?.type !== WIDGET_HEIGHT_MESSAGE) return;

		const reported = Number(event.data?.height);
		if (Number.isFinite(reported) && reported > 0) {
			height = Math.min(Math.max(Math.ceil(reported), MIN_HEIGHT), MAX_HEIGHT);
		}
	};

	onMount(() => {
		window.addEventListener('message', onMessage);
	});

	onDestroy(() => {
		window.removeEventListener('message', onMessage);
	});
</script>

<div
	class="w-full overflow-hidden rounded-2xl border border-gray-100 dark:border-gray-850 bg-white shadow-sm"
>
	<iframe
		bind:this={iframeEl}
		id={`widget-html-${id}`}
		title="widget"
		class="w-full border-0"
		style="height: {height}px"
		sandbox="allow-scripts"
		{srcdoc}
	></iframe>
</div>
