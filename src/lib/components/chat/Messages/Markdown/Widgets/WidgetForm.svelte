<script lang="ts">
	import { getContext } from 'svelte';
	import { fillTemplate, BRAND_BUTTON_CLASS, type FormWidget } from '$lib/utils/widgets';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	const i18n = getContext('i18n');

	export let widget: FormWidget;
	export let done = true;

	const widgetActions: { submit: (prompt: string) => void } | undefined =
		getContext('widgetActions');

	// Number inputs bind a number (or null when cleared), so values are not
	// guaranteed to be strings until asText() normalizes them.
	let values: Record<string, string | number | null> = {};
	let submitted = false;

	// Give selects an initial '' so the placeholder option is the one selected
	// (with bind:value, the `selected` attribute on the option is ignored).
	for (const field of widget.fields) {
		if (field.type === 'select') {
			values[field.name] = '';
		}
	}

	const asText = (value: string | number | null | undefined): string =>
		value == null ? '' : String(value).trim();

	$: enabled = !!widgetActions && done && !submitted;

	// A required checkbox must actually be checked, not merely touched.
	$: missingRequired = widget.fields.some(
		(field) =>
			field.required &&
			(field.type === 'checkbox' ? values[field.name] !== 'yes' : !asText(values[field.name]))
	);

	const inputClass =
		'w-full rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 outline-hidden focus:border-[#00a5ba] dark:focus:border-[#026c80] transition disabled:opacity-50';

	const onSubmit = () => {
		if (!enabled || missingRequired) return;

		const labels: Record<string, string> = {};
		const filled: Record<string, string> = {};
		for (const field of widget.fields) {
			labels[field.name] = field.label;
			filled[field.name] =
				field.type === 'checkbox'
					? values[field.name] === 'yes'
						? 'yes'
						: 'no'
					: asText(values[field.name]);
		}

		const prompt = fillTemplate(widget.template, filled, labels).trim();
		if (!prompt) return;

		submitted = true;
		widgetActions?.submit(prompt);
	};
</script>

<div
	class="w-full max-w-md rounded-2xl border border-gray-100 dark:border-gray-850 bg-white dark:bg-gray-900 shadow-sm overflow-hidden"
>
	<div class="h-1 w-full bg-gradient-to-r from-[#026c80] to-[#00a5ba]"></div>

	<form
		class="p-4 flex flex-col gap-3"
		on:submit|preventDefault={onSubmit}
	>
		{#if widget.title}
			<div class="font-semibold text-[#00313f] dark:text-gray-50 leading-snug">
				{widget.title}
			</div>
		{/if}

		{#each widget.fields as field}
			<label class="flex flex-col gap-1">
				<span class="text-xs font-medium text-gray-600 dark:text-gray-400">
					{field.label}{#if field.required}<span class="text-rose-500">*</span>{/if}
				</span>

				{#if field.type === 'select'}
					<select
						class={inputClass}
						bind:value={values[field.name]}
						disabled={!enabled}
						required={field.required}
					>
						<option value="" disabled hidden>
							{field.placeholder ?? $i18n.t('Select an option')}
						</option>
						{#each field.options ?? [] as option}
							<option value={option}>{option}</option>
						{/each}
					</select>
				{:else if field.type === 'textarea'}
					<textarea
						class="{inputClass} resize-none"
						rows="3"
						placeholder={field.placeholder ?? ''}
						bind:value={values[field.name]}
						disabled={!enabled}
						required={field.required}
					></textarea>
				{:else if field.type === 'checkbox'}
					<label class="inline-flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
						<input
							type="checkbox"
							class="size-4 rounded accent-[#026c80]"
							disabled={!enabled}
							on:change={(e) => {
								values[field.name] = e.currentTarget.checked ? 'yes' : 'no';
							}}
						/>
						{field.placeholder ?? field.label}
					</label>
				{:else if field.type === 'number'}
					<input
						type="number"
						class={inputClass}
						placeholder={field.placeholder ?? ''}
						bind:value={values[field.name]}
						disabled={!enabled}
						required={field.required}
					/>
				{:else if field.type === 'date'}
					<input
						type="date"
						class={inputClass}
						bind:value={values[field.name]}
						disabled={!enabled}
						required={field.required}
					/>
				{:else}
					<input
						type="text"
						class={inputClass}
						placeholder={field.placeholder ?? ''}
						bind:value={values[field.name]}
						disabled={!enabled}
						required={field.required}
					/>
				{/if}
			</label>
		{/each}

		<Tooltip content={!widgetActions ? $i18n.t('Actions unavailable here') : ''}>
			<button
				type="submit"
				class="w-full rounded-xl {BRAND_BUTTON_CLASS} px-3 py-2 text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed"
				disabled={!enabled || missingRequired}
			>
				{submitted ? $i18n.t('Sent') : (widget.submit ?? $i18n.t('Submit'))}
			</button>
		</Tooltip>
	</form>
</div>
