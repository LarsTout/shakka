<script lang="ts">
	import { goto } from '$app/navigation';
	import { session } from '#lib/auth.js';
	import { browserStorage } from '#lib/browser-storage.js';
	import { saveReturnTo } from '#lib/local-prefs.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	let handledFor: string | null = null; // plain variable, not $state: the returnPath already redirected for

	// Signed out: remember this exact link and log in first (A2). Signed in: straight to the form.
	// replace keeps /go out of the history, so Back does not loop (WP-14 N-4).
	$effect(() => {
		const s = $session;
		const returnPath = data.returnPath;
		if (s === undefined || handledFor === returnPath) return;
		handledFor = returnPath;
		if (s === null) {
			saveReturnTo(browserStorage(), returnPath, Date.now());
			void goto('/login', { replace: true });
		} else {
			void goto(data.target, { replace: true });
		}
	});
</script>

<svelte:head><title>Doorsturen · Shakka</title></svelte:head>

<p>Doorsturen…</p>
