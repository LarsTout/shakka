<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	// Temporary until the session-aware version: replace keeps the back button from returning to /go.
	onMount(() => {
		void goto(data.target, { replace: true });
	});
</script>

<svelte:head><title>Doorsturen · Shakka</title></svelte:head>

<p>Doorsturen…</p>
