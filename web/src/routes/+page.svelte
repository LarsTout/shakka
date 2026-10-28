<script lang="ts">
	import { refreshAll } from '$app/navigation';
	import { onMount } from 'svelte';
	import FavoriteStar from '#lib/components/FavoriteStar.svelte';
	import Freshness from '#lib/components/Freshness.svelte';
	import MapSwitch from '#lib/components/MapSwitch.svelte';
	import VerdictBadge from '#lib/components/VerdictBadge.svelte';
	import { daySummaryText, latestOfSummaries, shouldRefreshOnResume } from '#lib/view.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	let view = $state<'list' | 'map'>('list');

	onMount(() => {
		const onVisible = () => {
			if (document.visibilityState === 'visible' && shouldRefreshOnResume(data.now, Date.now())) {
				void refreshAll();
			}
		};
		document.addEventListener('visibilitychange', onVisible);
		return () => document.removeEventListener('visibilitychange', onVisible);
	});
</script>

<svelte:head><title>Spots · Shakka</title></svelte:head>

<h1>Spots</h1>
<p class="muted">
	Per spot het oordeel voor de daglichturen van vandaag en morgen, met de standaardgrenzen van de
	spot. Kies een spot voor het overzicht per uur.
</p>

{#if data.kind === 'error'}
	<div class="banner" role="alert">
		<p>De spots konden niet worden geladen. Controleer je verbinding.</p>
		<button type="button" onclick={() => refreshAll()}>Opnieuw proberen</button>
	</div>
{:else if data.spots.length === 0}
	<p>Er staan nog geen spots in de database.</p>
{:else}
	<Freshness latest={latestOfSummaries(data.summaries)} now={new Date(data.now)} />
	<MapSwitch spots={data.spots} summaries={data.summaries} bind:view />
	<ul class="spot-list" hidden={view === 'map'}>
		{#each data.spots as spot (spot.id)}
			{@const summary = data.summaries[spot.id]}
			<li class="spot-item" data-spot={spot.id}>
				<div class="spot-head">
					<div class="spot-title">
						<a class="spot-link" href="/spot/{spot.id}">{spot.name}</a>
						{#if spot.region}<span class="muted"> · {spot.region}</span>{/if}
						{#if !spot.verified}<span class="badge-unverified">niet geverifieerd</span>{/if}
					</div>
					<FavoriteStar spotId={spot.id} spotName={spot.name} />
				</div>
				{#if summary}
					<p class="day-summary day-today">
						<span class="day-label">Vandaag:</span>
						{#if summary.today.best}<VerdictBadge verdict={summary.today.best} size="lg" />{/if}
						<span class="day-text">{daySummaryText(summary.today, true)}</span>
					</p>
					<p class="day-summary">
						<span class="day-label">Morgen:</span>
						{#if summary.tomorrow.best}<VerdictBadge verdict={summary.tomorrow.best} />{/if}
						<span class="day-text">{daySummaryText(summary.tomorrow, false)}</span>
					</p>
				{:else}
					<p class="no-data muted">Nog geen data</p>
				{/if}
			</li>
		{/each}
	</ul>
{/if}
