<script lang="ts">
	import AlertRuleForm from '#lib/components/AlertRuleForm.svelte';
	import LoginPrompt from '#lib/components/LoginPrompt.svelte';
	import PushSettings from '#lib/components/PushSettings.svelte';
	import { session } from '#lib/auth.js';
	import { ALERT_DEFAULTS } from '#lib/contracts.js';
	import { ruleSummary, storedRuleStatus } from '#lib/forms.js';
	import { loadAlertsPage, type AlertsPageData } from '#lib/user-page-data.js';

	const userId = $derived($session ? $session.user.id : null);
	let page = $state<{ kind: 'idle' } | { kind: 'loading' } | AlertsPageData>({ kind: 'idle' });
	let token = 0;

	function load(id: string) {
		const t = ++token;
		page = { kind: 'loading' };
		void loadAlertsPage(id).then((r) => {
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
</script>

<svelte:head><title>Alerts · Shakka</title></svelte:head>

<h1>Alerts</h1>

{#if $session !== undefined}
	<PushSettings signedIn={$session !== null} />
{/if}

{#if $session === undefined}
	<p class="muted">Laden…</p>
{:else if $session === null}
	<LoginPrompt reason="je alerts in te stellen" />
{:else if page.kind === 'idle' || page.kind === 'loading'}
	<p class="muted">Laden…</p>
{:else if page.kind === 'error'}
	<div class="banner" role="alert">
		<p>De alertinstellingen konden niet worden geladen. Controleer je verbinding.</p>
		<button type="button" onclick={retry}>Opnieuw proberen</button>
	</div>
{:else if page.kind === 'ok' && userId !== null}
	<p class="muted">
		Voor elke favoriete spot staat een alert standaard aan, met de standaardinstellingen. Lege
		velden volgen de standaard. Je eigen windgrenzen voor alle spots stel je in bij je
		<a href="/profiel">profiel</a>. Haal je een spot uit je favorieten, dan verdwijnen ook de
		alertinstellingen voor die spot.
	</p>
	{#if page.entries.length === 0}
		<p>
			Je hebt nog geen favorieten. Tik op de ster bij een spot in de <a href="/">lijst</a> om hem toe
			te voegen.
		</p>
	{:else}
		{#each page.entries as e (e.spot.id)}
			{@const st = storedRuleStatus(e.rule, {
				spot: e.spot,
				profile: page.profile,
				defaults: ALERT_DEFAULTS
			})}
			<section class="alert-rule" data-spot={e.spot.id} aria-labelledby="rule-{e.spot.id}">
				<h2 id="rule-{e.spot.id}"><a href="/spot/{e.spot.id}">{e.spot.name}</a></h2>
				{#if !e.spot.verified}<p class="notice">
						Deze spot is nog niet geverifieerd. Je krijgt er pas alerts voor als het spotprofiel is
						gecontroleerd.
					</p>{/if}
				{#if st.ok}<p class="rule-summary">{ruleSummary(st.rule)}</p>{:else}<p
						class="banner warning"
						role="note"
					>
						{st.problem}
					</p>{/if}
				<details>
					<summary>Instellingen aanpassen</summary>
					<AlertRuleForm
						{userId}
						spot={e.spot}
						profile={page.profile}
						row={e.rule}
						onsaved={(row) => (e.rule = row)}
					/>
				</details>
			</section>
		{/each}
	{/if}
{/if}
