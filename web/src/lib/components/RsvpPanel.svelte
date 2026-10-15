<script lang="ts">
	import { createRsvp, deleteRsvp, getPublicSession, updateRsvp } from '#lib/rsvp.js';
	import {
		browserStorage,
		clearStoredRsvp,
		readStoredRsvp,
		writeStoredRsvp
	} from '#lib/rsvp-storage.js';
	import {
		SESSION_RETENTION_DAYS,
		type PublicRsvp,
		type PublicSession,
		type RsvpUpdateInput,
		type StoredRsvp
	} from '#lib/rsvp-types.js';
	import {
		RSVP_MESSAGES,
		RSVP_NOTICES,
		RsvpError,
		emptyRsvpForm,
		rideLabel,
		rsvpFormFromRsvp,
		type RsvpErrorKind
	} from '#lib/session-view.js';
	import RsvpForm from './RsvpForm.svelte';

	let {
		slug,
		rsvps,
		closed,
		stored = $bindable(),
		onrefresh
	}: {
		slug: string;
		rsvps: PublicRsvp[];
		closed: boolean;
		stored: StoredRsvp | null;
		onrefresh: (fresh: PublicSession | null) => void;
	} = $props();

	let mode = $state<'view' | 'edit' | 'confirm_delete'>('view');
	let busy = $state(false);
	let error = $state<string | null>(null);
	let notice = $state<string | null>(null);
	let serverClosed = $state(false); // A5: the server said session_closed; never reset

	const isClosed = $derived(closed || serverClosed);
	const me = $derived(stored ? (rsvps.find((r) => r.id === stored!.rsvp_id) ?? null) : null);
	const byId = $derived(new Map(rsvps.map((r) => [r.id, r])));
	const drivers = $derived(rsvps.filter((r) => r.ride === 'offers_ride' && r.id !== stored?.rsvp_id));

	function kindOf(e: unknown): RsvpErrorKind {
		return e instanceof RsvpError ? e.kind : 'unknown';
	}

	async function refresh() {
		try {
			const fresh = await getPublicSession(slug);
			if (fresh === null) {
				clearStoredRsvp(browserStorage(), slug);
				stored = null;
			}
			onrefresh(fresh);
		} catch {
			console.warn('session refresh failed');
		}
	}

	async function create(value: RsvpUpdateInput) {
		if (busy) return;
		busy = true;
		error = null;
		notice = null;
		try {
			const existing = readStoredRsvp(browserStorage(), slug);
			if (existing) {
				// Another tab already signed up (A15): no second RSVP.
				stored = existing;
				await refresh();
				return;
			}
			const res = await createRsvp(slug, {
				first_name: value.first_name,
				ride: value.ride,
				seats_offered: value.seats_offered
			});
			const ok = writeStoredRsvp(browserStorage(), slug, res);
			stored = res;
			notice = ok ? RSVP_NOTICES.created : RSVP_NOTICES.storageFailed;
			await refresh();
		} catch (e) {
			const k = kindOf(e);
			error = RSVP_MESSAGES[k];
			if (k === 'session_closed') serverClosed = true;
			if (k === 'session_closed' || k === 'session_full') await refresh();
		} finally {
			busy = false;
		}
	}

	async function save(value: RsvpUpdateInput) {
		if (busy || !stored) return;
		busy = true;
		error = null;
		notice = null;
		try {
			await updateRsvp(stored.edit_token, value);
			mode = 'view';
			notice = RSVP_NOTICES.updated;
			await refresh();
		} catch (e) {
			const k = kindOf(e);
			if (k === 'invalid_token') {
				clearStoredRsvp(browserStorage(), slug);
				stored = null;
				mode = 'view';
				error = RSVP_MESSAGES.invalid_token;
				await refresh();
			} else if (k === 'session_closed') {
				serverClosed = true;
				mode = 'view';
				error = RSVP_MESSAGES.session_closed;
				await refresh();
			} else {
				error = RSVP_MESSAGES[k];
			}
		} finally {
			busy = false;
		}
	}

	async function remove() {
		if (busy || !stored) return;
		busy = true;
		error = null;
		notice = null;
		try {
			const removed = await deleteRsvp(stored.edit_token);
			clearStoredRsvp(browserStorage(), slug);
			stored = null;
			mode = 'view';
			notice = removed ? RSVP_NOTICES.deleted : RSVP_NOTICES.alreadyDeleted;
			await refresh();
		} catch (e) {
			error = RSVP_MESSAGES[kindOf(e)];
			mode = 'view';
		} finally {
			busy = false;
		}
	}
</script>

{#if stored || !isClosed || notice || error}
	<section class="rsvp-panel" aria-labelledby={stored || !isClosed ? 'rsvp-heading' : undefined}>
		{#if stored}
			<h2 id="rsvp-heading">Jij gaat</h2>
			{#if me}
				{@const ride = rideLabel(me, byId)}
				<p>
					Aangemeld als <bdi>{me.first_name}</bdi> · {ride.label}{#if ride.name}{' '}<bdi>{ride.name}</bdi>{/if}
				</p>
			{/if}
			<p class="muted">Wijzigen of afmelden kan alleen in deze browser op dit apparaat.</p>
			{#if mode === 'edit' && me && !isClosed}
				<RsvpForm
					mode="edit"
					initial={rsvpFormFromRsvp(me)}
					{drivers}
					{busy}
					onsubmit={save}
					oncancel={() => (mode = 'view')}
				/>
			{:else if mode === 'confirm_delete'}
				<p>Weet je zeker dat je je wilt afmelden?</p>
				<button type="button" disabled={busy} onclick={remove}>Ja, afmelden</button>
				<button type="button" disabled={busy} onclick={() => (mode = 'view')}>Nee</button>
			{:else}
				{#if me && !isClosed}<button type="button" disabled={busy} onclick={() => (mode = 'edit')}
						>Wijzigen</button
					>{/if}
				<button type="button" disabled={busy} onclick={() => (mode = 'confirm_delete')}>Afmelden</button>
			{/if}
		{:else if !isClosed}
			<h2 id="rsvp-heading">Ga je mee?</h2>
			<p>Tik "Ik ook" met alleen je voornaam. Je hebt geen account nodig.</p>
			<RsvpForm mode="create" initial={emptyRsvpForm()} drivers={[]} {busy} onsubmit={create} />
			<p class="hint" id="rsvp-privacy">
				Alleen je voornaam en je vervoerskeuze worden opgeslagen, tot {SESSION_RETENTION_DAYS} dagen na
				de sessie. Iedereen met deze link kan ze zien. Wijzigen of afmelden kan later alleen in deze
				browser op dit apparaat. <a href="/privacy">Meer over privacy</a>
			</p>
		{/if}
		{#if notice}<p class="notice-ok" role="status">{notice}</p>{/if}
		{#if error}<p class="error" role="alert">{error}</p>{/if}
	</section>
{/if}
