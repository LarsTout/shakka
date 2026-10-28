<script lang="ts">
	import { refreshAll } from '$app/navigation';
	import { onMount } from 'svelte';
	import DayTimeline from '#lib/components/DayTimeline.svelte';
	import Attribution from '#lib/components/Attribution.svelte';
	import FavoriteStar from '#lib/components/FavoriteStar.svelte';
	import Freshness from '#lib/components/Freshness.svelte';
	import HourVerdict from '#lib/components/HourVerdict.svelte';
	import {
		NOT_FILLED_NL,
		TIDE_SENSITIVITY_LABEL_NL,
		formatLevelCm,
		seasonText,
		statusLabel,
		tideText
	} from '#lib/labels.js';
	import { session } from '#lib/auth.js';
	import { goHref, goRuns } from '#lib/go.js';
	import { WAVES_NOTE_NL, marineByHour, waveText } from '#lib/marine.js';
	import { formatLocal, localDateKey } from '#lib/time.js';
	import { dayTabLabel, dayTimeline } from '#lib/timeline.js';
	import type { MarineHour } from '#lib/types.js';
	import {
		dayHeading,
		groupByLocalDay,
		latestEvaluatedAt,
		shouldRefreshOnResume,
		tidesForDay,
		visibleHours
	} from '#lib/view.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	let showDark = $state(false);
	let selectedDay = $state<string | null>(null);

	// Narrowed on kind === 'ok' so the error and not_found states never touch these (review N-1).
	const now = $derived(new Date(data.now));
	const todayKey = $derived(localDateKey(now));
	const groups = $derived(data.kind === 'ok' ? groupByLocalDay(data.evaluations) : []);
	const activeDay = $derived(
		groups.some((g) => g.dateKey === selectedDay) ? selectedDay : (groups[0]?.dateKey ?? null)
	);
	const latest = $derived(data.kind === 'ok' ? latestEvaluatedAt(data.evaluations) : null);
	const station = $derived(data.kind === 'ok' ? data.spot.rws_station?.trim() || null : null);

	const waves = $derived(
		data.kind === 'ok' ? marineByHour(data.marine, now) : new Map<number, MarineHour>()
	);
	// The note only shows when at least one wave line is visible (review N-3).
	const anyWaveVisible = $derived(
		groups.some((g) =>
			visibleHours(g.hours, showDark).some((e) => waves.has(Date.parse(e.valid_at)))
		)
	);

	const title = $derived(
		data.kind === 'ok'
			? data.spot.name
			: data.kind === 'not_found'
				? 'Spot niet gevonden'
				: 'Spot'
	);

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

<svelte:head><title>{title} · Shakka</title></svelte:head>

{#if data.kind === 'not_found'}
	<h1>Spot niet gevonden</h1>
	<p>Deze spot bestaat niet (meer).</p>
	<p><a href="/">Naar alle spots</a></p>
{:else if data.kind === 'error'}
	<h1>Spot</h1>
	<div class="banner" role="alert">
		<p>De gegevens konden niet worden geladen. Controleer je verbinding.</p>
		<button type="button" onclick={() => refreshAll()}>Opnieuw proberen</button>
	</div>
{:else}
	{@const spot = data.spot}
	<p><a class="back-link" href="/">Alle spots</a></p>
	<div class="title-row">
		<h1>{spot.name}</h1>
		<FavoriteStar spotId={spot.id} spotName={spot.name} />
	</div>
	{#if spot.region}<p class="muted">{spot.region}</p>{/if}

	{#if !spot.verified}
		<div class="banner unverified" role="note">
			<p>
				<strong>Niet geverifieerd.</strong> Dit spotprofiel is nog niet gecontroleerd. Richting, regels
				en getij kunnen ontbreken of onjuist zijn. Check ter plekke altijd de lokale regels.
			</p>
		</div>
	{/if}

	<p class="muted">
		Het oordeel gebruikt de standaardgrenzen van deze spot, niet je eigen alertinstellingen.
	</p>
	<Freshness {latest} {now} showUpdated />
	{#if anyWaveVisible}<p class="muted waves-note">{WAVES_NOTE_NL}</p>{/if}

	{#if groups.length === 0}
		<p class="no-data">Nog geen data voor deze spot.</p>
	{:else}
		<button type="button" aria-pressed={showDark} onclick={() => (showDark = !showDark)}>
			{showDark ? 'Verberg donkere uren' : 'Toon ook donkere uren'}
		</button>
		<div class="day-tabs" role="group" aria-label="Dag">
			{#each groups as g (g.dateKey)}
				<button
					type="button"
					aria-pressed={g.dateKey === activeDay}
					aria-controls="dagpaneel-{g.dateKey}"
					onclick={() => (selectedDay = g.dateKey)}>{dayTabLabel(g.dateKey, todayKey)}</button
				>
			{/each}
		</div>
		{#each groups as g (g.dateKey)}
			{@const dayTides = tidesForDay(data.tides, g.dateKey)}
			{@const hours = visibleHours(g.hours, showDark)}
			{@const runs = goRuns(g.hours)}
			{@const tl = dayTimeline(g.hours, {
				tides: dayTides,
				now: g.dateKey === todayKey ? now : undefined
			})}
			<section
				class="day"
				class:day-inactive={g.dateKey !== activeDay}
				id="dagpaneel-{g.dateKey}"
				aria-labelledby="dag-{g.dateKey}"
			>
				<h2 id="dag-{g.dateKey}">{dayHeading(g.dateKey, todayKey)}</h2>
				{#if tl}<DayTimeline timeline={tl} size="lg" />{/if}
				{#if station}
					<p class="tides">
						Getij: {dayTides.length ? dayTides.map(tideText).join(' · ') : 'geen gegevens'}
					</p>
				{/if}
				{#if $session && runs.length}
					<ul class="go-runs">
						{#each runs as r (r.start.getTime())}
							<li>
								<a class="go-run" href={goHref(spot.id, r.start, r.end)}
									>Ik ga {formatLocal(r.start, 'time')}–{formatLocal(r.end, 'time')}</a
								>
							</li>
						{/each}
					</ul>
				{/if}
				{#if hours.length}
					<ol class="hours">
						{#each hours as e (e.valid_at)}
							{@const wave = waves.get(Date.parse(e.valid_at))}
							<li>
								<HourVerdict evaluation={e} />
								{#if wave}<p class="waves">{waveText(wave)}</p>{/if}
							</li>
						{/each}
					</ol>
				{:else}
					<p class="muted">Geen uren met daglicht.</p>
				{/if}
			</section>
		{/each}
	{/if}

	<section class="spot-profile">
		<h2>Over deze spot</h2>
		<dl>
			<dt>Status</dt>
			<dd>{statusLabel(spot.status)}</dd>
			<dt>Seizoenssluiting</dt>
			<dd>
				{#if spot.season.length === 0}
					Geen seizoenssluiting bekend
				{:else}
					<ul>
						{#each spot.season as c, i (i)}<li>{seasonText(c)}</li>{/each}
					</ul>
				{/if}
			</dd>
			<dt>Getijvoorkeur</dt>
			<dd>
				{TIDE_SENSITIVITY_LABEL_NL[spot.tide_sensitive]}{#if spot.tide_min_level_cm !== null},
					minimaal {formatLevelCm(spot.tide_min_level_cm)} cm NAP{/if}
			</dd>
			<dt>Getijstation</dt>
			<dd>{station ?? NOT_FILLED_NL}</dd>
			<dt>Gevaren</dt>
			<dd>
				{#if spot.hazards}<span class="prewrap">{spot.hazards}</span>{:else}{NOT_FILLED_NL}{/if}
			</dd>
			<dt>Notities</dt>
			<dd>
				{#if spot.notes}<span class="prewrap">{spot.notes}</span>{:else}{NOT_FILLED_NL}{/if}
			</dd>
		</dl>
	</section>

	<section class="sources">
		<h2>Bronnen</h2>
		<Attribution />
	</section>
{/if}
