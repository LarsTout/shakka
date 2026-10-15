<script lang="ts">
	import { refreshAll } from '$app/navigation';
	import { onMount } from 'svelte';
	import Attribution from '#lib/components/Attribution.svelte';
	import Freshness from '#lib/components/Freshness.svelte';
	import HourVerdict from '#lib/components/HourVerdict.svelte';
	import RsvpPanel from '#lib/components/RsvpPanel.svelte';
	import SessionParticipants from '#lib/components/SessionParticipants.svelte';
	import { browserStorage } from '#lib/browser-storage.js';
	import { clearStoredRsvp, readStoredRsvp } from '#lib/rsvp-storage.js';
	import { SESSION_RETENTION_DAYS, type PublicSession, type StoredRsvp } from '#lib/rsvp-types.js';
	import { isSessionClosed, optionalText, sessionWindowText, tikkieLink } from '#lib/session-view.js';
	import { formatDateKey } from '#lib/time.js';
	import { groupByLocalDay, latestEvaluatedAt, shouldRefreshOnResume } from '#lib/view.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	// Overridable deriveds (Svelte >= 5.25, A8): a mutation refresh replaces them; a new load resets them.
	let session = $derived(data.kind === 'ok' ? data.session : null);
	let rsvps = $derived(data.kind === 'ok' ? data.rsvps : []);
	let gone = $derived(data.kind !== 'ok');
	let now = $derived(new Date(data.now));

	let stored = $state<StoredRsvp | null>(null);
	let storageReady = $state(false);
	let checkedSlug: string | null = null; // not reactive on purpose (A7: check once per slug)

	const closed = $derived(session !== null && isSessionClosed(session, now));
	const ended = $derived(session !== null && !session.cancelled && closed);
	const groups = $derived(data.kind === 'ok' && data.evaluations ? groupByLocalDay(data.evaluations) : []);
	const latest = $derived(data.kind === 'ok' && data.evaluations ? latestEvaluatedAt(data.evaluations) : null);
	const spotName = $derived(session?.spot_name ?? 'Onbekende spot');
	const tikkie = $derived(tikkieLink(session?.tikkie_url ?? null));
	const note = $derived(optionalText(session?.note ?? null));

	// Storage (A7): read the stored RSVP on every new load; on the first load of a slug, drop a stale key.
	$effect(() => {
		const d = data;
		const storage = browserStorage();
		if (d.kind === 'ok') {
			let s = readStoredRsvp(storage, d.slug);
			if (checkedSlug !== d.slug) {
				checkedSlug = d.slug;
				if (s !== null && !d.rsvps.some((r) => r.id === s!.rsvp_id)) {
					clearStoredRsvp(storage, d.slug);
					s = null;
				}
			}
			stored = s;
		} else {
			if (d.kind === 'not_found') clearStoredRsvp(storage, d.slug);
			stored = null;
		}
		storageReady = true;
	});

	function applyRefresh(fresh: PublicSession | null) {
		now = new Date();
		if (fresh) {
			session = fresh.session;
			rsvps = fresh.rsvps;
		} else {
			gone = true;
		}
	}

	// Clock (A5): close the form by itself after ends_at.
	$effect(() => {
		if (!session || closed) return;
		const ms = Date.parse(session.ends_at) - Date.now();
		if (ms > 2_147_483_647) return; // beyond the setTimeout range; a later load or resume handles it
		const id = setTimeout(
			() => {
				now = new Date();
			},
			Math.max(0, ms) + 1_000
		);
		return () => clearTimeout(id);
	});

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

<svelte:head>
	<meta name="robots" content="noindex" />
	<title
		>{data.kind === 'ok'
			? `Kitesessie ${spotName}`
			: data.kind === 'not_found'
				? 'Sessie niet gevonden'
				: 'Sessie'} · Shakka</title
	>
</svelte:head>

{#if data.kind === 'not_found' || (gone && data.kind === 'ok')}
	<h1>Sessie niet gevonden</h1>
	<p>Deze sessie bestaat niet (meer). Sessies verdwijnen {SESSION_RETENTION_DAYS} dagen na afloop.</p>
	<p><a href="/">Naar alle spots</a></p>
{:else if data.kind === 'error'}
	<h1>Sessie</h1>
	<div class="banner" role="alert">
		<p>De sessie kon niet worden geladen. Controleer je verbinding.</p>
		<button type="button" onclick={() => refreshAll()}>Opnieuw proberen</button>
	</div>
{:else if session}
	<h1>Kitesessie: {spotName}</h1>
	<p class="session-when">{sessionWindowText(session.starts_at, session.ends_at)}</p>
	<p class="session-organizer">Georganiseerd door <bdi>{session.organizer_name}</bdi></p>
	{#if session.cancelled}
		<div class="banner warning" role="alert">
			<p><strong>Deze sessie is geannuleerd.</strong> Aanmelden kan niet meer. Afmelden kan nog wel.</p>
		</div>
	{:else if ended}
		<div class="banner" role="note"><p>Deze sessie is voorbij. Aanmelden kan niet meer.</p></div>
	{/if}
	<p><a href="/spot/{encodeURIComponent(session.spot_id)}">Naar de spotpagina van {spotName}</a></p>
	{#if note}
		<section class="session-note"><h2>Notitie</h2><p class="prewrap"><bdi>{note}</bdi></p></section>
	{/if}
	{#if tikkie}
		<p class="session-tikkie">
			Kosten delen: <a href={tikkie} target="_blank" rel="noopener noreferrer">Open betaalverzoek</a>
			<span class="muted">(link naar tikkie.me)</span>
		</p>
	{/if}

	{#if storageReady}
		{#key data.slug}
			<RsvpPanel slug={data.slug} {rsvps} {closed} bind:stored onrefresh={applyRefresh} />
		{/key}
	{/if}

	<SessionParticipants {session} {rsvps} myRsvpId={stored?.rsvp_id ?? null} />

	<section class="session-hours" aria-labelledby="oordeel">
		<h2 id="oordeel">Oordeel per uur</h2>
		<p class="muted">Met de standaardgrenzen van de spot, niet met persoonlijke instellingen.</p>
		{#if !closed}<Freshness {latest} {now} showUpdated />{/if}
		{#if data.kind === 'ok' && data.evaluations === null}
			<p class="no-data">Het oordeel kon niet worden geladen.</p>
		{:else if groups.length === 0}
			<p class="no-data">Er is nog geen oordeel voor dit tijdvenster.</p>
		{:else}
			{#each groups as g (g.dateKey)}
				{#if groups.length > 1}<h3>{formatDateKey(g.dateKey, 'day')}</h3>{/if}
				<ol class="hours">
					{#each g.hours as e (e.valid_at)}<li><HourVerdict evaluation={e} /></li>{/each}
				</ol>
			{/each}
		{/if}
	</section>

	<section class="sources"><h2>Bronnen</h2><Attribution /></section>
{/if}
