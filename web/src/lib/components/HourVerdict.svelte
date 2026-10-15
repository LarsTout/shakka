<script lang="ts">
	import { confidenceLabel, dirClassLabel, reasonLabel } from '#lib/contracts.js';
	import { directionText, windText } from '#lib/labels.js';
	import { formatLocal } from '#lib/time.js';
	import type { Evaluation } from '#lib/types.js';
	import VerdictBadge from './VerdictBadge.svelte';
	import WindArrow from './WindArrow.svelte';

	let { evaluation: e }: { evaluation: Evaluation } = $props();
</script>

<div class="hour">
	<time datetime={e.valid_at}>{formatLocal(new Date(e.valid_at), 'time')}</time>
	<VerdictBadge verdict={e.verdict} />
	<span class="wind">{windText(e.wind_kn, e.gust_kn)}</span>
	<span class="direction"><WindArrow deg={e.dir_deg} /> {directionText(e.dir_deg)}</span>
	<span class="dir-class">{e.dir_class ? dirClassLabel(e.dir_class) : 'Richtingsklasse onbekend'}</span>
	<span class="confidence"
		>Betrouwbaarheid: {e.confidence ? confidenceLabel(e.confidence) : 'onbekend'}</span
	>
	{#if e.reasons.length}
		<ul class="reasons">
			{#each e.reasons as r (r)}<li>{reasonLabel(r)}</li>{/each}
		</ul>
	{/if}
</div>
