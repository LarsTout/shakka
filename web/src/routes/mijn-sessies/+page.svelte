<script lang="ts">
	import LoginPrompt from '#lib/components/LoginPrompt.svelte';
	import SessionForm from '#lib/components/SessionForm.svelte';
	import { session } from '#lib/auth.js';
	import { sessionToForm } from '#lib/session-form.js';
	import { sessionPath, type NewSession } from '#lib/session-model.js';
	import {
		loadMySessionsPage,
		type MySessionEntry,
		type MySessionsPageData
	} from '#lib/session-page-data.js';
	import {
		SESSION_ERROR_MESSAGES,
		cancelSession,
		sessionErrorMessage,
		updateSession
	} from '#lib/sessions.js';
	import { formatWindowLocal } from '#lib/time.js';

	const userId = $derived($session ? $session.user.id : null);
	let page = $state<{ kind: 'idle' } | { kind: 'loading' } | MySessionsPageData>({ kind: 'idle' });
	let token = 0;
	let confirmId = $state<string | null>(null);
	let busyId = $state<string | null>(null);
	let messages = $state<Record<string, string>>({});

	function load(id: string) {
		const t = ++token;
		page = { kind: 'loading' };
		void loadMySessionsPage(id, new Date()).then((r) => {
			if (t === token) page = r;
		});
	}
	function retry() {
		if (userId !== null) load(userId);
	}
	$effect(() => {
		const id = userId;
		if (id === null) {
			token++;
			page = { kind: 'idle' };
			return;
		}
		load(id);
	});

	async function saveEdit(e: MySessionEntry, v: NewSession): Promise<string | null> {
		try {
			await updateSession(e.session.id, v);
			e.session = { ...e.session, ...v };
			return null;
		} catch (err) {
			return sessionErrorMessage(err);
		}
	}

	async function cancel(e: MySessionEntry) {
		const id = e.session.id;
		busyId = id;
		try {
			const now = new Date();
			await cancelSession(id, now);
			e.session = { ...e.session, cancelled_at: now.toISOString() };
			messages[id] = 'Sessie geannuleerd.';
		} catch (err) {
			messages[id] =
				sessionErrorMessage(err) === SESSION_ERROR_MESSAGES.notFound
					? SESSION_ERROR_MESSAGES.notFound
					: SESSION_ERROR_MESSAGES.cancelFailed;
		} finally {
			busyId = null;
			confirmId = null;
		}
	}
</script>

<svelte:head><title>Mijn sessies · Shakka</title></svelte:head>

<h1>Mijn sessies</h1>

{#if $session === undefined}
	<p class="muted">Laden…</p>
{:else if $session === null}
	<LoginPrompt reason="je sessies te zien" />
{:else if page.kind === 'idle' || page.kind === 'loading'}
	<p class="muted">Laden…</p>
{:else if page.kind === 'error'}
	<div class="banner" role="alert">
		<p>Je sessies konden niet worden geladen. Controleer je verbinding.</p>
		<button type="button" onclick={retry}>Opnieuw proberen</button>
	</div>
{:else}
	<p><a class="share-button" href="/sessie/nieuw">Nieuwe sessie</a></p>
	{#if page.entries.length === 0}
		<p>
			Je hebt geen komende sessies. Tik bij een spot op "Ik ga" of maak hier een nieuwe sessie.
		</p>
	{/if}
	{#each page.entries as e (e.session.id)}
		{@const edit = sessionToForm(e.session)}
		<section class="my-session" data-slug={e.session.slug} aria-labelledby="sessie-{e.session.id}">
			<h2 id="sessie-{e.session.id}">{e.spotName}</h2>
			<p>{formatWindowLocal(new Date(e.session.starts_at), new Date(e.session.ends_at))}</p>
			{#if e.session.cancelled_at}
				<p class="banner warning" role="note">Geannuleerd</p>
			{:else}
				<p>
					<a href="/sessie/{e.session.slug}/delen">Delen</a> ·
					<a href={sessionPath(e.session.slug)}>Sessiepagina</a>
				</p>
				<details>
					<summary>Bewerken</summary>
					<SessionForm
						mode="edit"
						idPrefix={e.session.id}
						spots={page.spots}
						initial={edit.form}
						preferred={edit.preferred}
						onsave={(v) => saveEdit(e, v)}
					/>
				</details>
				{#if confirmId === e.session.id}
					<p>Weet je het zeker? Wie de link heeft, ziet dat de sessie is geannuleerd.</p>
					<button type="button" disabled={busyId === e.session.id} onclick={() => cancel(e)}
						>Ja, annuleer de sessie</button
					>
					<button type="button" onclick={() => (confirmId = null)}>Nee</button>
				{:else}
					<button type="button" onclick={() => (confirmId = e.session.id)}>Sessie annuleren</button>
				{/if}
			{/if}
			<p><a href="/sessie/{e.session.slug}/beheer">Aanmeldingen beheren</a></p>
			{#if messages[e.session.id]}<p role="status">{messages[e.session.id]}</p>{/if}
		</section>
	{/each}
{/if}
