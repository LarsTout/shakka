<script lang="ts">
	import { session, signInWithMagicLink, signInWithPastedLink } from '#lib/auth.js';
	import { isStandalone, needsInstallFirst } from '#lib/platform.js';

	const standalone = isStandalone();
	const installHint = needsInstallFirst();

	let email = $state('');
	let status = $state<'idle' | 'sending' | 'sent'>('idle');
	let error = $state<string | null>(null);
	let sentTo = $state('');
	let link = $state('');
	let linkBusy = $state(false);
	let linkError = $state<string | null>(null);

	async function submitLink(e: SubmitEvent) {
		e.preventDefault();
		if (linkBusy) return;
		linkError = null;
		linkBusy = true;
		const r = await signInWithPastedLink(link);
		linkBusy = false;
		if (r.error) linkError = r.error;
		else link = '';
	}

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		if (status === 'sending') return;
		error = null;
		status = 'sending';
		const result = await signInWithMagicLink(email);
		if (result.error) {
			error = result.error;
			status = 'idle';
		} else {
			sentTo = email.trim();
			status = 'sent';
		}
	}
</script>

<svelte:head><title>Inloggen · Shakka</title></svelte:head>

{#if $session}
	<h1>Inloggen</h1>
	<p>Je bent ingelogd als {$session.user.email}.</p>
	<p><a href="/">Naar de start</a></p>
{:else if status === 'sent'}
	<h1>Check je mail</h1>
	<p>
		We hebben een inloglink gestuurd naar {sentTo}.
		{#if standalone}
			Tik de link in de mail niet aan, maar kopieer hem en plak hem hieronder bij ‘Inloglink plakken’.
		{:else}
			Open de link op dit apparaat om in te loggen.
		{/if}
	</p>
	<button type="button" onclick={() => (status = 'idle')}>Ander e-mailadres</button>
{:else}
	<h1>Inloggen</h1>
	<p>Je krijgt een link per mail. Een wachtwoord is niet nodig.</p>
	{#if installHint}
		<p class="notice">
			Op iPhone of iPad en wil je meldingen? Zet Shakka dan eerst op je beginscherm (deelknop, ‘Zet op
			beginscherm’) en log in vanuit die app. Inloggen hier in Safari geldt niet voor de app op je beginscherm.
		</p>
	{/if}
	<form novalidate onsubmit={submit}>
		<label for="email">E-mailadres</label>
		<input
			id="email"
			name="email"
			type="email"
			autocomplete="email"
			inputmode="email"
			required
			bind:value={email}
		/>
		<button type="submit" disabled={status === 'sending'}>
			{status === 'sending' ? 'Bezig met versturen…' : 'Stuur inloglink'}
		</button>
		{#if error}
			<p role="alert" class="error">{error}</p>
		{/if}
	</form>
{/if}

{#if $session === null && standalone}
	<section class="paste-link" aria-labelledby="paste-link-title">
		<h2 id="paste-link-title">Inloglink plakken</h2>
		<p class="hint">
			De link uit de mail opent in Safari, niet in deze app. Tik hem daarom niet aan, maar kopieer hem en
			plak hem hieronder.
		</p>
		<p class="notice" id="paste-link-preview">
			Let op: de link werkt maar één keer, en een voorvertoning van de link gebruikt hem al op. Zet daarom
			eerst de linkvoorvertoningen uit: houd in je mail-app een link in een ándere mail ingedrukt en kies
			‘Verberg linkvoorvertoningen’. Houd daarna de inloglink ingedrukt en kies ‘Kopieer link’. Zie je
			toch een voorbeeld van de pagina, dan is de link gebruikt; vraag dan een nieuwe aan. Of kopieer de
			link op je computer en plak hem hier via het gedeelde klembord (niet via WhatsApp of Berichten: die
			laden ook een voorvertoning).
		</p>
		<form novalidate onsubmit={submitLink}>
			<label for="magic-link">Inloglink</label>
			<input
				id="magic-link"
				name="magic-link"
				type="url"
				inputmode="url"
				autocomplete="off"
				aria-describedby="paste-link-preview"
				bind:value={link}
			/>
			<button type="submit" disabled={linkBusy}>Inloggen met link</button>
			{#if linkError}<p role="alert" class="error">{linkError}</p>{/if}
		</form>
	</section>
{/if}
