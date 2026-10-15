<script lang="ts">
	import { formatLocal } from '#lib/time.js';
	import { isStale } from '#lib/view.js';

	let {
		latest,
		now,
		showUpdated = false
	}: { latest: Date | null; now: Date; showUpdated?: boolean } = $props();
</script>

{#if latest !== null}
	{#if isStale(latest, now)}
		<div class="banner warning" role="alert">
			<p>
				Let op: deze verwachting is ouder dan 3 uur (bijgewerkt {formatLocal(latest, 'dateTime')}).
				De gegevens kunnen verouderd zijn.
			</p>
		</div>
	{:else if showUpdated}
		<p class="muted">Bijgewerkt: {formatLocal(latest, 'dateTime')}</p>
	{/if}
{/if}
