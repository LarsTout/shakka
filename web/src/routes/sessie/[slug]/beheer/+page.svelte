<script lang="ts">
	import LoginPrompt from '#lib/components/LoginPrompt.svelte';
	import { session } from '#lib/auth.js';
	import {
		MODERATION_MESSAGES,
		deleteRsvpAsOrganizer,
		setRsvpsClosed
	} from '#lib/moderation.js';
	import type { PublicRsvp } from '#lib/rsvp-types.js';
	import { sessionPath } from '#lib/session-model.js';
	import { loadManagePage, type ManagePageData } from '#lib/session-page-data.js';
	import { sessionErrorMessage } from '#lib/sessions.js';
	import { rideLabel } from '#lib/session-view.js';
	import { formatWindowLocal } from '#lib/time.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const userId = $derived($session ? $session.user.id : null);
	let page = $state<{ kind: 'idle' } | { kind: 'loading' } | ManagePageData>({ kind: 'idle' });
	let token = 0;

	// Local copies of what the page edits; set when a load finishes.
	let rsvps = $state<PublicRsvp[]>([]);
	let rsvpsClosed = $state(false);
	let toggling = $state(false);
	let toggleError = $state('');
	let confirmId = $state<string | null>(null);
	let deleting = $state(false);
	let message = $state('');

	function load() {
		const t = ++token;
		page = { kind: 'loading' };
		void loadManagePage(data.slug).then((r) => {
			if (t !== token) return;
			if (r.kind === 'ok') {
				rsvps = r.rsvps;
				rsvpsClosed = r.rsvpsClosed;
				toggleError = '';
				confirmId = null;
				message = '';
			}
			page = r;
		});
	}
	function retry() {
		if (userId !== null) load();
	}
	$effect(() => {
		if (userId === null) {
			token++;
			page = { kind: 'idle' };
			return;
		}
		load();
	});

	async function toggle(sessionId: string) {
		if (toggling) return;
		toggling = true;
		toggleError = '';
		try {
			await setRsvpsClosed(sessionId, !rsvpsClosed);
			rsvpsClosed = !rsvpsClosed;
		} catch (err) {
			toggleError = sessionErrorMessage(err);
		} finally {
			toggling = false;
		}
	}

	async function remove(id: string) {
		if (deleting) return;
		deleting = true;
		const res = await deleteRsvpAsOrganizer(id);
		deleting = false;
		confirmId = null;
		if (res.ok) {
			rsvps = rsvps.filter((r) => r.id !== id);
			message = MODERATION_MESSAGES.deleted;
		} else if (res.error === MODERATION_MESSAGES.alreadyGone) {
			rsvps = rsvps.filter((r) => r.id !== id);
			message = MODERATION_MESSAGES.alreadyGone;
		} else {
			message = res.error ?? MODERATION_MESSAGES.failed;
		}
	}
</script>

<svelte:head><title>Aanmeldingen beheren · Shakka</title></svelte:head>

<h1>Aanmeldingen beheren</h1>

{#if $session === undefined}
	<p class="muted">Laden…</p>
{:else if $session === null}
	<LoginPrompt reason="aanmeldingen te beheren" />
{:else if page.kind === 'idle' || page.kind === 'loading'}
	<p class="muted">Laden…</p>
{:else if page.kind === 'error'}
	<div class="banner" role="alert">
		<p>De sessie kon niet worden geladen. Controleer je verbinding.</p>
		<button type="button" onclick={retry}>Opnieuw proberen</button>
	</div>
{:else if page.kind === 'not_found'}
	<p><strong>Sessie niet gevonden.</strong> Deze sessie bestaat niet (meer), of je bent niet de organisator.</p>
	<p><a href="/mijn-sessies">Naar mijn sessies</a></p>
{:else}
	{@const s = page.session}
	{@const byId = new Map(rsvps.map((r) => [r.id, r]))}
	<p class="session-summary">
		<strong>{page.spotName}</strong> · {formatWindowLocal(new Date(s.starts_at), new Date(s.ends_at))}
	</p>
	{#if s.cancelled_at !== null}
		<div class="banner warning" role="note"><p>Deze sessie is geannuleerd.</p></div>
	{/if}
	{#if s.cancelled_at === null && Date.parse(s.ends_at) > Date.now()}
		<section aria-labelledby="signup-heading">
			<h2 id="signup-heading">Aanmelden</h2>
			<p>{rsvpsClosed ? MODERATION_MESSAGES.closed : MODERATION_MESSAGES.open}</p>
			<button type="button" disabled={toggling} onclick={() => toggle(s.id)}>
				{rsvpsClosed ? MODERATION_MESSAGES.openButton : MODERATION_MESSAGES.closeButton}
			</button>
			{#if toggleError}<p role="status">{toggleError}</p>{/if}
		</section>
	{/if}
	<section aria-labelledby="rsvps-heading">
		<h2 id="rsvps-heading">Aanmeldingen ({rsvps.length})</h2>
		{#if rsvps.length === 0}
			<p>Nog niemand heeft zich aangemeld.</p>
		{:else}
			<ul class="manage-list">
				{#each rsvps as r (r.id)}
					{@const ride = rideLabel(r, byId)}
					<li>
						<span
							><bdi id="rsvp-name-{r.id}">{r.first_name}</bdi> · {ride.label}{#if ride.name}{' '}<bdi
									>{ride.name}</bdi
								>{/if}</span
						>
						{#if confirmId === r.id}
							<p>
								Aanmelding van <bdi>{r.first_name}</bdi> verwijderen? Diegene krijgt hier geen bericht van.
							</p>
							<button type="button" disabled={deleting} onclick={() => remove(r.id)}
								>Ja, verwijderen</button
							>
							<button type="button" disabled={deleting} onclick={() => (confirmId = null)}>Nee</button>
						{:else}
							<button
								type="button"
								aria-describedby="rsvp-name-{r.id}"
								onclick={() => (confirmId = r.id)}>Verwijderen</button
							>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
		{#if message}<p role="status">{message}</p>{/if}
	</section>
	<p><a href={sessionPath(s.slug)}>Sessiepagina</a> · <a href="/mijn-sessies">Mijn sessies</a></p>
{/if}

<style>
	.manage-list {
		list-style: none;
		padding: 0;
	}
	.manage-list li {
		padding: 0.5rem 0;
		border-bottom: 1px solid #ccc;
	}
	.manage-list button,
	section > button {
		min-height: 2.75rem;
	}
</style>
