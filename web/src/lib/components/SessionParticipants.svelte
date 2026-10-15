<script lang="ts">
	import type { PublicRsvp, PublicSessionInfo } from '#lib/rsvp-types.js';
	import { carpoolView, rideLabel, seatsText } from '#lib/session-view.js';

	let {
		session,
		rsvps,
		myRsvpId
	}: { session: PublicSessionInfo; rsvps: PublicRsvp[]; myRsvpId: string | null } = $props();

	const byId = $derived(new Map(rsvps.map((r) => [r.id, r])));
	const carpool = $derived(carpoolView(session, rsvps));
</script>

<section class="participants" aria-labelledby="deelnemers">
	<h2 id="deelnemers">Deelnemers ({rsvps.length + 1})</h2>
	<ul class="participant-list">
		<li class="organizer"><bdi>{session.organizer_name}</bdi> <span class="muted">organisator</span></li>
		{#each rsvps as r (r.id)}
			{@const ride = rideLabel(r, byId)}
			<li data-rsvp={r.id}>
				<bdi>{r.first_name}</bdi>{#if r.id === myRsvpId}{' '}<span class="muted">(jij)</span>{/if}
				<span class="ride"> · {ride.label}{#if ride.name}{' '}<bdi>{ride.name}</bdi>{/if}</span>
			</li>
		{/each}
	</ul>
</section>
<section class="carpool" aria-labelledby="carpool">
	<h2 id="carpool">Carpool</h2>
	{#if carpool.organizerSeats !== null}
		<p>Vrije plekken bij <bdi>{session.organizer_name}</bdi>: {carpool.organizerSeats}</p>
	{/if}
	{#if carpool.departurePoint}<p>Vertrekpunt: <bdi>{carpool.departurePoint}</bdi></p>{/if}
	{#if carpool.drivers.length}
		<h3>Biedt een lift aan</h3>
		<ul class="carpool-drivers">
			{#each carpool.drivers as d (d.rsvp.id)}
				<li data-driver={d.rsvp.id}>
					<bdi>{d.rsvp.first_name}</bdi> · {seatsText(d.rsvp.seats_offered)}{#if d.riders.length}{' '}· meerijders: {#each d.riders as m, i (m.id)}{#if i > 0}{', '}{/if}<bdi>{m.first_name}</bdi>{/each}{/if}
				</li>
			{/each}
		</ul>
	{/if}
	{#if carpool.seekers.length}
		<h3>Zoekt een lift</h3>
		<ul class="carpool-seekers">
			{#each carpool.seekers as s (s.id)}<li data-seeker={s.id}><bdi>{s.first_name}</bdi></li>{/each}
		</ul>
	{/if}
	{#if carpool.isEmpty}<p class="muted">Nog niemand heeft iets over vervoer doorgegeven.</p>{/if}
</section>
