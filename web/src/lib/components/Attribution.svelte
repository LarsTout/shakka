<script lang="ts">
	let { compact = false }: { compact?: boolean } = $props();
</script>

{#snippet link(href: string, text: string)}
	<a {href} target="_blank" rel="noopener noreferrer">{text}</a>
{/snippet}

<section class="attribution" aria-label="Bronvermelding">
	{#if compact}
		<p class="compact">
			{@render link('https://open-meteo.com/', 'Weather data by Open-Meteo.com')}
			({@render link('https://creativecommons.org/licenses/by/4.0/', 'CC BY 4.0')}) · Modellen:
			{@render link('https://www.knmi.nl/', 'KNMI')},
			{@render link('https://www.dwd.de/', 'DWD')},
			{@render link('https://www.ecmwf.int/', 'ECMWF')},
			{@render link('https://www.noaa.gov/', 'NOAA')} · Getij:
			{@render link('https://rijkswaterstaatdata.nl/waterdata/', 'Rijkswaterstaat')}
		</p>
	{:else}
		<p>
			{@render link('https://open-meteo.com/', 'Weather data by Open-Meteo.com')}, gelicenseerd onder
			{@render link('https://creativecommons.org/licenses/by/4.0/', 'CC BY 4.0')}. Shakka rekent de
			data om naar knopen en beoordeelt ze per spot.
		</p>
		<p>
			Weermodellen van {@render link('https://www.knmi.nl/', 'KNMI')},
			{@render link('https://www.dwd.de/', 'DWD')},
			{@render link('https://www.ecmwf.int/', 'ECMWF')} en
			{@render link('https://www.noaa.gov/', 'NOAA')}, en golfmodellen van
			{@render link('https://www.dwd.de/', 'DWD')} en
			{@render link('https://www.ecmwf.int/', 'ECMWF')}, via Open-Meteo.
		</p>
		<p>
			Getijdata: {@render link('https://rijkswaterstaatdata.nl/waterdata/', 'Rijkswaterstaat')} (CC0).
		</p>
	{/if}
</section>
