<script lang="ts">
	// SVG icon library — single-stroke, currentColor.
	// Verbatim port of icons.jsx from the PRP-2 design handoff.

	type Props = {
		name: string;
		size?: number;
		stroke?: number;
		className?: string;
	};

	let { name, size = 16, stroke = 1.6, className = '' }: Props = $props();
</script>

<svg
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width={stroke}
	stroke-linecap="round"
	stroke-linejoin="round"
	class={className}
>
	{#if name === 'grid'}
		<rect x="3" y="3" width="7" height="7" rx="1.2" />
		<rect x="14" y="3" width="7" height="7" rx="1.2" />
		<rect x="3" y="14" width="7" height="7" rx="1.2" />
		<rect x="14" y="14" width="7" height="7" rx="1.2" />
	{:else if name === 'sidebar'}
		<rect x="3" y="3" width="18" height="18" rx="2" />
		<path d="M9 3v18" />
	{:else if name === 'pencil'}
		<path d="M12 20h9" />
		<path d="M16.5 3.5a2.121 2.121 0 113 3L7 19l-4 1 1-4 12.5-12.5z" />
	{:else if name === 'search'}
		<circle cx="11" cy="11" r="7" />
		<path d="M21 21l-4.3-4.3" />
	{:else if name === 'notes'}
		<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
		<path d="M14 2v6h6" />
		<path d="M9 13h6M9 17h4" />
	{:else if name === 'workspace'}
		<rect x="3" y="3" width="7" height="7" rx="1" />
		<rect x="14" y="3" width="7" height="7" rx="1" />
		<rect x="3" y="14" width="7" height="7" rx="1" />
		<rect x="14" y="14" width="7" height="7" rx="1" />
	{:else if name === 'plus'}
		<path d="M12 5v14M5 12h14" />
	{:else if name === 'sliders'}
		<line x1="4" y1="21" x2="4" y2="14" />
		<line x1="4" y1="10" x2="4" y2="3" />
		<line x1="12" y1="21" x2="12" y2="12" />
		<line x1="12" y1="8" x2="12" y2="3" />
		<line x1="20" y1="21" x2="20" y2="16" />
		<line x1="20" y1="12" x2="20" y2="3" />
		<line x1="1" y1="14" x2="7" y2="14" />
		<line x1="9" y1="8" x2="15" y2="8" />
		<line x1="17" y1="16" x2="23" y2="16" />
	{:else if name === 'sparkle'}
		<path d="M12 3l1.7 4.7L18 9.5l-4.3 1.8L12 16l-1.7-4.7L6 9.5l4.3-1.8L12 3z" />
		<path
			d="M19 16l.7 1.8L21.5 18.5l-1.8.7L19 21l-.7-1.8L16.5 18.5l1.8-.7L19 16z"
			opacity=".7"
		/>
	{:else if name === 'mic'}
		<rect x="9" y="2" width="6" height="12" rx="3" />
		<path d="M5 10v1a7 7 0 0014 0v-1" />
		<line x1="12" y1="19" x2="12" y2="22" />
	{:else if name === 'waveform'}
		<line x1="2" y1="12" x2="2" y2="12" />
		<line x1="6" y1="8" x2="6" y2="16" />
		<line x1="10" y1="5" x2="10" y2="19" />
		<line x1="14" y1="8" x2="14" y2="16" />
		<line x1="18" y1="3" x2="18" y2="21" />
		<line x1="22" y1="10" x2="22" y2="14" />
	{:else if name === 'upload'}
		<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
		<polyline points="17 8 12 3 7 8" />
		<line x1="12" y1="3" x2="12" y2="15" />
	{:else if name === 'file'}
		<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
		<polyline points="14 2 14 8 20 8" />
	{:else if name === 'fileText'}
		<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
		<polyline points="14 2 14 8 20 8" />
		<line x1="9" y1="13" x2="15" y2="13" />
		<line x1="9" y1="17" x2="13" y2="17" />
	{:else if name === 'check'}
		<polyline points="20 6 9 17 4 12" />
	{:else if name === 'x'}
		<line x1="18" y1="6" x2="6" y2="18" />
		<line x1="6" y1="6" x2="18" y2="18" />
	{:else if name === 'user'}
		<path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
		<circle cx="12" cy="7" r="4" />
	{:else if name === 'chevR'}
		<polyline points="9 18 15 12 9 6" />
	{:else if name === 'chevL'}
		<polyline points="15 18 9 12 15 6" />
	{:else if name === 'chevD'}
		<polyline points="6 9 12 15 18 9" />
	{:else if name === 'arrowR'}
		<line x1="5" y1="12" x2="19" y2="12" />
		<polyline points="12 5 19 12 12 19" />
	{:else if name === 'send'}
		<line x1="22" y1="2" x2="11" y2="13" />
		<polygon points="22 2 15 22 11 13 2 9 22 2" />
	{:else if name === 'refresh'}
		<polyline points="23 4 23 10 17 10" />
		<polyline points="1 20 1 14 7 14" />
		<path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
	{:else if name === 'brain'}
		<path
			d="M9.5 2A2.5 2.5 0 0112 4.5v15a2.5 2.5 0 01-4.96.44 2.5 2.5 0 01-2.96-3.08 3 3 0 01-.34-5.58 2.5 2.5 0 011.32-4.24 2.5 2.5 0 014.44-1.04z"
		/>
		<path
			d="M14.5 2A2.5 2.5 0 0012 4.5v15a2.5 2.5 0 004.96.44 2.5 2.5 0 002.96-3.08 3 3 0 00.34-5.58 2.5 2.5 0 00-1.32-4.24 2.5 2.5 0 00-4.44-1.04z"
		/>
	{:else if name === 'shield'}
		<path d="M12 2L4 6v6c0 5 3.5 9 8 10 4.5-1 8-5 8-10V6l-8-4z" />
	{:else if name === 'bolt'}
		<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
	{:else if name === 'eye'}
		<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
		<circle cx="12" cy="12" r="3" />
	{:else if name === 'alert'}
		<path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
		<line x1="12" y1="9" x2="12" y2="13" />
		<line x1="12" y1="17" x2="12" y2="17" />
	{:else if name === 'clock'}
		<circle cx="12" cy="12" r="10" />
		<polyline points="12 6 12 12 16 14" />
	{:else if name === 'download'}
		<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
		<polyline points="7 10 12 15 17 10" />
		<line x1="12" y1="15" x2="12" y2="3" />
	{:else if name === 'quote'}
		<path
			d="M3 21c3 0 7-1 7-8V5c0-1-1-2-2-2H4c-1 0-2 1-2 2v6c0 1 1 2 2 2h3c0 4-1 6-4 6v2zm14 0c3 0 7-1 7-8V5c0-1-1-2-2-2h-4c-1 0-2 1-2 2v6c0 1 1 2 2 2h3c0 4-1 6-4 6v2z"
		/>
	{:else if name === 'filter'}
		<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
	{:else if name === 'paperclip'}
		<path
			d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"
		/>
	{:else if name === 'book'}
		<path d="M4 19.5A2.5 2.5 0 016.5 17H20" />
		<path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
	{:else if name === 'folder'}
		<path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
	{/if}
</svg>
