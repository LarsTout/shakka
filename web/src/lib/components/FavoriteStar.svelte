<script lang="ts">
	import { favorites, toggleFavorite } from '#lib/favorites.js';

	let { spotId, spotName }: { spotId: string; spotName: string } = $props();
	let busy = $state(false);
	let failed = $state(false);

	const status = $derived($favorites.status);
	const pressed = $derived($favorites.status === 'ready' && $favorites.ids.has(spotId));

	async function toggle() {
		busy = true;
		failed = !(await toggleFavorite(spotId));
		busy = false;
	}
</script>

{#if status !== 'unknown' && status !== 'signed_out'}
	<button
		type="button"
		class="favorite-star"
		aria-pressed={pressed}
		aria-label="Favoriet: {spotName}"
		title={status === 'error'
			? 'Favorieten konden niet worden geladen'
			: pressed
				? 'Verwijder uit favorieten'
				: 'Voeg toe aan favorieten'}
		disabled={status !== 'ready' || busy}
		onclick={toggle}
	>
		<span aria-hidden="true">{pressed ? '★' : '☆'}</span>
	</button>
	{#if failed}<span class="error" role="status">Niet opgeslagen</span>{/if}
{/if}
