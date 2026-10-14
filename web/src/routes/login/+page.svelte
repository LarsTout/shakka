<script lang="ts">
	import { session, signInWithMagicLink } from '#lib/auth.js';

	let email = $state('');
	let status = $state<'idle' | 'sending' | 'sent'>('idle');
	let error = $state<string | null>(null);
	let sentTo = $state('');

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
		We hebben een inloglink gestuurd naar {sentTo}. Open de link op dit apparaat om in te loggen.
	</p>
	<button type="button" onclick={() => (status = 'idle')}>Ander e-mailadres</button>
{:else}
	<h1>Inloggen</h1>
	<p>Je krijgt een link per mail. Een wachtwoord is niet nodig.</p>
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
