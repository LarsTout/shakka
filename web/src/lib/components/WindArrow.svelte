<script lang="ts">
	let { deg }: { deg: number | null } = $props();
</script>

<svg
	class="wind-arrow"
	viewBox="0 0 32 32"
	width="28"
	height="28"
	aria-hidden="true"
	focusable="false"
>
	<circle cx="16" cy="16" r="15" fill="none" stroke="currentColor" stroke-opacity="0.4" />
	<g font-size="6" text-anchor="middle" fill="currentColor">
		<text x="16" y="6">N</text>
		<text x="27" y="18">O</text>
		<text x="16" y="30">Z</text>
		<text x="5" y="18">W</text>
	</g>
	{#if deg !== null}
		<!-- Points where the wind blows to: wind from 270 -> arrow towards the east. -->
		<g transform="rotate({(deg + 180) % 360} 16 16)">
			<line x1="16" y1="24" x2="16" y2="10" stroke="currentColor" stroke-width="2" />
			<polygon points="16,6 12,12 20,12" fill="currentColor" />
		</g>
	{/if}
</svg>
