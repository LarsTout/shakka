<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { goTarget } from '#lib/go.js';

	// Safety net: the load in +page.ts normally redirects before this renders. replace keeps the
	// back button from returning to /go (review N-4).
	onMount(() => {
		void goto(goTarget(new URL(page.url.href)), { replace: true });
	});
</script>

<svelte:head><title>Doorsturen · Shakka</title></svelte:head>

<p>Doorsturen…</p>
