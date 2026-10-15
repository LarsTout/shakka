<script lang="ts">
	import { onMount } from 'svelte';
	import {
		MAPLIBRE_URL,
		MAPTILER_COPYRIGHT_URL,
		MAPTILER_HOME_URL,
		MAPTILER_LOGO_URL,
		OSM_COPYRIGHT_URL,
		type MapFailure
	} from '#lib/map/config.js';
	import { markerModels } from '#lib/map/markers.js';
	import { getMaptilerKey, loadMapLibre, supportsWebGL2 } from '#lib/map/platform.js';
	import { startMap, type MapController } from '#lib/map/start.js';
	import type { Spot, SpotSummary } from '#lib/types.js';

	interface Props {
		spots: Spot[];
		summaries: Record<string, SpotSummary>;
		onfail?: (reason: MapFailure) => void;
	}
	let { spots, summaries, onfail }: Props = $props();

	let container: HTMLDivElement;
	let ready = $state(false);
	let controller: MapController | null = null;
	const notOnMap = $derived(markerModels(spots, summaries).withoutCoords);

	onMount(() => {
		controller = startMap(
			container,
			spots,
			summaries,
			{ key: getMaptilerKey(), webgl: supportsWebGL2, load: loadMapLibre },
			{ onReady: () => (ready = true), onFail: (r) => onfail?.(r) }
		);
		return () => {
			controller?.destroy();
			controller = null;
		};
	});

	$effect(() => {
		const s = spots;
		const su = summaries;
		controller?.update(s, su);
	});
</script>

<section class="map-wrap" aria-label="Kaart met spots">
	<div class="map-canvas" bind:this={container}></div>
	{#if ready}
		<a class="maptiler-logo" href={MAPTILER_HOME_URL} target="_blank" rel="noopener noreferrer">
			<img src={MAPTILER_LOGO_URL} alt="MapTiler logo" />
		</a>
	{:else}
		<p class="map-loading" role="status">Kaart laden…</p>
	{/if}
</section>
<p class="map-attribution">
	Kaart: <a href={MAPTILER_COPYRIGHT_URL} target="_blank" rel="noopener noreferrer">© MapTiler</a> ·
	<a href={OSM_COPYRIGHT_URL} target="_blank" rel="noopener noreferrer">© OpenStreetMap contributors</a> ·
	<a href={MAPLIBRE_URL} target="_blank" rel="noopener noreferrer">MapLibre</a>. De kaarttegels komen van
	MapTiler.
</p>
<p class="map-legend muted">
	Tik op een spot voor het overzicht per uur. Gestippelde rand: spot niet geverifieerd.
</p>
{#if notOnMap > 0}
	<p class="muted">
		{notOnMap === 1 ? '1 spot zonder coördinaten staat' : `${notOnMap} spots zonder coördinaten staan`} niet
		op de kaart.
	</p>
{/if}

<style>
	.map-wrap {
		position: relative;
	}
	.map-canvas {
		width: 100%;
		height: min(70vh, 32rem);
	}
	.map-loading {
		position: absolute;
		inset: 0;
		margin: 0;
		display: grid;
		place-items: center;
		background: #f4f4f4;
	}
	.maptiler-logo {
		position: absolute;
		left: 10px;
		bottom: 10px;
		z-index: 999;
	}
	:global(.map-marker) {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.15rem 0.35rem;
		background: #fff;
		color: #1a1a1a;
		border: 1px solid #555;
		border-radius: 0.25rem;
		font-size: 0.8rem;
		text-decoration: none;
		white-space: nowrap;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
	}
	:global(.map-marker-unverified) {
		border-style: dashed;
	}
	:global(.verdict-none) {
		background: #555;
	}
	:global(.map-marker .sr-only) {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}
</style>
