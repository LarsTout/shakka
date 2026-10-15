<script lang="ts">
	import {
		PUSH_MESSAGES,
		disablePush,
		enablePush,
		getPushStatus,
		needsInstallFirst,
		type PushStatus
	} from '#lib/push.js';

	let { signedIn }: { signedIn: boolean } = $props();

	const installFirst = needsInstallFirst(); // once, at init (CSR only)
	let status = $state<PushStatus | 'loading'>('loading');
	let busy = $state(false);
	let message = $state<{ kind: 'status' | 'alert'; text: string } | null>(null);
	let token = 0;

	async function refresh() {
		const t = ++token;
		status = 'loading';
		const s = await getPushStatus();
		if (t === token) status = s;
	}

	$effect(() => {
		if (signedIn && !installFirst) void refresh();
		else {
			token++;
			status = 'loading';
			message = null;
		}
	});

	// enablePush is called synchronously from the click so iOS sees a user gesture.
	function turnOn() {
		if (busy) return;
		busy = true;
		message = null;
		void enablePush().then((r) => {
			busy = false;
			if (r.ok) {
				status = 'on';
				message = { kind: 'status', text: PUSH_MESSAGES.enabled };
				return;
			}
			if (r.error === PUSH_MESSAGES.denied) {
				status = 'denied'; // shown once, by the status branch
				message = null;
				return;
			}
			message = { kind: 'alert', text: r.error ?? PUSH_MESSAGES.subscribeFailed };
		});
	}

	async function turnOff() {
		if (busy) return;
		busy = true;
		message = null;
		await disablePush();
		busy = false;
		status = 'off';
		message = { kind: 'status', text: PUSH_MESSAGES.disabled };
	}
</script>

{#if installFirst || signedIn}
	<section class="push-settings" aria-labelledby="push-title">
		<h2 id="push-title">Meldingen op dit apparaat</h2>
		{#if installFirst}
			<p class="notice">{PUSH_MESSAGES.installFirst}</p>
		{:else if status === 'loading'}
			<p class="muted">Meldingen controleren…</p>
		{:else if status === 'unsupported' || status === 'unavailable' || status === 'denied' || status === 'needs_install'}
			<p class="notice">{PUSH_MESSAGES[status === 'needs_install' ? 'installFirst' : status]}</p>
		{:else if status === 'error'}
			<div class="banner" role="alert">
				<p>{PUSH_MESSAGES.statusFailed}</p>
				<button type="button" onclick={refresh}>Opnieuw proberen</button>
			</div>
		{:else if status === 'off'}
			<p>{PUSH_MESSAGES.intro}</p>
			<p class="hint">{PUSH_MESSAGES.newWindowsOnly}</p>
			<button type="button" disabled={busy} onclick={turnOn}>Meldingen aanzetten</button>
		{:else}
			<p>{PUSH_MESSAGES.on}</p>
			<button type="button" disabled={busy} onclick={turnOff}>Meldingen uitzetten</button>
		{/if}
		{#if message}
			<p role={message.kind} class:error={message.kind === 'alert'}>{message.text}</p>
		{/if}
	</section>
{/if}
