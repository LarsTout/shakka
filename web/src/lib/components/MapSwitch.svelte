<script lang="ts">
	import MapView from '#lib/components/MapView.svelte';
	import { MAP_FAILURE_MESSAGE_NL, preflight, type MapFailure, type ViewMode } from '#lib/map/config.js';
	import { getMaptilerKey, supportsWebGL2 } from '#lib/map/platform.js';
	import type { Spot, SpotSummary } from '#lib/types.js';

	interface Props {
		spots: Spot[];
		summaries: Record<string, SpotSummary>;
		view?: ViewMode;
	}
	let { spots, summaries, view = $bindable<ViewMode>('list') }: Props = $props();
	let notice = $state<string | null>(null);

	function showList() {
		view = 'list';
		notice = null;
	}
	function showMap() {
		if (view === 'map') return;
		const failure = preflight(getMaptilerKey(), supportsWebGL2);
		if (failure) {
			fail(failure);
			return;
		}
		notice = null;
		view = 'map';
	}
	function fail(reason: MapFailure) {
		view = 'list';
		notice = MAP_FAILURE_MESSAGE_NL[reason];
	}
</script>

<div class="view-toggle" role="group" aria-label="Weergave">
	<button type="button" aria-pressed={view === 'list'} onclick={showList}>Lijst</button>
	<button type="button" aria-pressed={view === 'map'} onclick={showMap}>Kaart</button>
</div>
{#if notice}<p class="banner map-notice" role="status">{notice}</p>{/if}
{#if view === 'map'}<MapView {spots} {summaries} onfail={fail} />{/if}
