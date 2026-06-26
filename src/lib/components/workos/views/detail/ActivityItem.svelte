<script lang="ts">
	import { displayName } from '../../lib/store';
	import { activityLabel } from '../../lib/activity';
	import type { Activity } from '../../lib/types';

	export let activity: Activity;
</script>

<div class="flex items-center gap-2 text-xs text-gray-400 py-1">
	<span class="w-1.5 h-1.5 rounded-full bg-gray-300 dark:bg-gray-600 flex-none"></span>
	<span>{activityLabel(activity, displayName)}</span>
</div>
