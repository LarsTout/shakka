<script lang="ts">
	import {
		ALERT_STATE_RETENTION_HOURS,
		FORECAST_RETENTION_HOURS,
		PRIVACY_CONTACT_EMAIL,
		PRIVACY_UPDATED_NL,
		RETURN_TO_TTL_MINUTES,
		SUPABASE_API_LOG_RETENTION_NL,
		SUPABASE_AUTH_LOG_RETENTION_NL
	} from '#lib/privacy.js';
	import { SESSION_RETENTION_DAYS } from '#lib/rsvp-types.js';
</script>

<svelte:head><title>Privacy · Shakka</title></svelte:head>

<h1>Privacy</h1>
<p class="muted">Laatst bijgewerkt: {PRIVACY_UPDATED_NL}</p>
<p>
	Shakka is een gratis app zonder advertenties, gemaakt en beheerd door Lars Toutenhoofd. Shakka
	bewaart zo weinig mogelijk over jou. Hieronder staat wat, waarom, hoe lang, en hoe je het weghaalt.
</p>

<h2>Kort</h2>
<ul>
	<li>Geen advertenties, geen analytics, geen trackers. Shakka zet zelf geen cookies.</li>
	<li>Shakka vraagt nooit om je locatie.</li>
	<li>De weerdata komt van de server van Shakka. Je browser praat nooit met Open-Meteo.</li>
	<li>Je account en alles wat eraan vastzit, verwijder je zelf op je <a href="/profiel">profielpagina</a>.</li>
</ul>

<h2>Waarom Shakka dit mag</h2>
<p>
	Shakka verwerkt deze gegevens om de dienst te leveren die je zelf aanvraagt: inloggen, je alerts,
	meldingen, en de sessies die je organiseert of waarvoor je je aanmeldt. Meldingen krijg je pas als
	je ze zelf aanzet. De logs bij Supabase en Cloudflare zijn nodig om de dienst veilig te laten werken.
	Shakka gebruikt geen tracking en vraagt daarom niet om toestemming voor cookies.
</p>

<h2>Wat Shakka bewaart als je inlogt</h2>
<ul>
	<li>
		<strong>E-mailadres</strong>, om je een inloglink te sturen en je te herkennen. Supabase, de
		database- en inlogdienst van Shakka, bewaart daarbij wanneer je account is gemaakt en wanneer je
		voor het laatst inlogde, en per ingelogd apparaat technische gegevens zoals het tijdstip, je
		IP-adres en je browser. Tot je je account verwijdert.
	</li>
	<li>
		<strong>Profiel</strong>, alles optioneel: je gewicht, niveau, kitematen en standaard windgrenzen.
		Voor het kite-advies en je alerts. Tot je het aanpast of je account verwijdert.
	</li>
	<li>
		<strong>Favorieten en alertinstellingen</strong>: welke spots, en per spot je windgrenzen,
		windrichtingen, dagen en tijden. Tot je ze weghaalt of je account verwijdert.
	</li>
	<li>
		<strong>Verstuurde alerts</strong>: per spot en tijdvak wat je laatste melding was, zodat je niet
		twee keer hetzelfde krijgt. Verdwijnt {ALERT_STATE_RETENTION_HOURS} uur na het einde van het tijdvak.
	</li>
	<li>
		<strong>Push-abonnementen</strong>: per apparaat waarop je meldingen aanzet, een adres en sleutels
		van de pushdienst van je browser. Verdwijnt als je meldingen uitzet, als je uitlogt, als de
		pushdienst meldt dat het adres niet meer werkt, of als je je account verwijdert.
	</li>
	<li>
		<strong>Sessies die je organiseert</strong>: je voornaam, de spot, het tijdvak, en wat je verder
		invult (notitie, vertrekpunt, vrije plekken, Tikkie-link). Iedereen met de link kan dit zien.
		Verdwijnt {SESSION_RETENTION_DAYS} dagen na het einde van de sessie, of eerder als je je account
		verwijdert.
	</li>
</ul>

<h2>Als je je aanmeldt voor een sessie</h2>
<p>
	Voor "Ik ook" heb je geen account nodig. Shakka bewaart dan alleen je <strong>voornaam</strong> en
	je keuze voor vervoer: eigen vervoer, een lift zoeken of plekken aanbieden, en met wie je meerijdt.
	Iedereen met de link kan dit zien. Het verdwijnt als je je afmeldt of als de organisator je aanmelding verwijdert, en anders
	{SESSION_RETENTION_DAYS} dagen na het einde van de sessie. In de database van Shakka staat geen
	e-mailadres of IP-adres bij je aanmelding.
</p>

<h2>Weerdata</h2>
<p>
	Verwachtingen, getij en oordelen per spot zijn geen persoonsgegevens. Shakka bewaart ze tot
	{FORECAST_RETENTION_HOURS} uur na het uur waar ze over gaan.
</p>

<h2>Op je eigen apparaat</h2>
<p>
	Een paar dingen staan in de opslag van je browser (localStorage). Ze blijven op je apparaat. Je
	wist ze met "Websitegegevens wissen" in je browser.
</p>
<ul>
	<li>Je inlogsessie. Verdwijnt als je uitlogt.</li>
	<li>De voornaam die je als organisator invulde, zodat je hem niet opnieuw hoeft te typen.</li>
	<li>
		Na "Ik ga" als je nog niet bent ingelogd: de spot en het tijdvak, zodat je na het inloggen verder
		kunt. Dit wordt gewist zodra je op dit apparaat inlogt. Log je niet in, dan gebruikt Shakka het na
		{RETURN_TO_TTL_MINUTES} minuten niet meer, en wist het de eerstvolgende keer dat je Shakka opent.
	</li>
	<li>
		Per sessie waarvoor je je aanmeldde: een code waarmee je je aanmelding kunt wijzigen of
		afmelden. Die verdwijnt als je je afmeldt, of als je de sessiepagina opent nadat de sessie is
		verwijderd. Anders blijft hij staan tot je je browsergegevens wist; je aanmelding zelf is dan al
		verwijderd.
	</li>
	<li>De bestanden van de app zelf, zodat Shakka ook offline opent. Daarin staat niets over jou.</li>
</ul>
<p>
	Daarnaast houdt je browser zelf een paar dingen bij, zoals bij elke website: per tabblad de
	scrollpositie (verdwijnt als je het tabblad sluit), en in de gewone browsercache bijvoorbeeld
	kaarttegels van MapTiler. Shakka slaat daar zelf niets in op.
</p>

<h2>Wie er nog meer iets ziet</h2>
<ul>
	<li>
		<strong>Supabase</strong> host de database en het inloggen, in een datacenter in de EU. Verzoeken
		van de app worden daar gelogd, onder andere met je IP-adres, en {SUPABASE_API_LOG_RETENTION_NL}
		bewaard. Inloglogs worden {SUPABASE_AUTH_LOG_RETENTION_NL} bewaard.
	</li>
	<li>
		<strong>Cloudflare</strong> host de app en ziet daarbij je IP-adres, om de pagina's te kunnen
		leveren. Shakka gebruikt geen analytics van Cloudflare.
	</li>
	<li>
		<strong>GitHub</strong> draait elk uur de berekening van oordelen en alerts. Die leest daarvoor je
		profiel, favorieten, alertinstellingen, push-abonnementen en welke alerts je al kreeg. In de logs
		komen geen persoonsgegevens.
	</li>
	<li>
		<strong>De pushdienst van je browser</strong> (bijvoorbeeld van Apple, Google, Mozilla of
		Microsoft) bezorgt je meldingen. De inhoud is versleuteld; de pushdienst ziet wel dat er een
		melding naar je apparaat gaat.
	</li>
	<li>
		<strong>MapTiler</strong> levert de kaart. Pas als je op "Kaart" tikt, haalt je browser kaartdata
		op bij MapTiler. MapTiler ziet dan je IP-adres, je browser en dat je van Shakka komt (het domein,
		niet de pagina). Zonder kaart praat je browser niet met MapTiler.
	</li>
	<li>
		<strong>De maildienst</strong> die de inloglink verstuurt, krijgt je e-mailadres. Nu is dat
		Supabase zelf.
	</li>
	<li>
		Links naar andere sites (bronnen, WhatsApp, Tikkie) openen die sites. Shakka stuurt daarbij niet
		mee van welke pagina je komt.
	</li>
	<li>De beheerder heeft technisch toegang tot de database, om problemen op te lossen.</li>
</ul>

<h2>Account verwijderen</h2>
<p>
	Op je <a href="/profiel">profielpagina</a> staat "Account verwijderen". Shakka verwijdert dan direct
	en definitief: je e-mailadres en login, je profiel, favorieten, alertinstellingen, verstuurde
	alerts, de push-abonnementen van al je apparaten, en de sessies die je organiseert, met de
	aanmeldingen daarvoor. Aanmeldingen die je zonder account bij sessies van anderen deed, hangen niet
	aan je account: meld je af op de sessiepagina, of ze verdwijnen {SESSION_RETENTION_DAYS} dagen na
	de sessie. Logs bij Supabase verlopen vanzelf (zie hierboven). Wat Cloudflare als hostingdienst
	bijhoudt, valt onder het privacybeleid van Cloudflare.
</p>

<h2>Je rechten</h2>
<p>
	Je mag weten welke gegevens Shakka over je heeft, en je mag ze laten verbeteren of verwijderen. Het
	meeste kun je zelf in de app.
	{#if PRIVACY_CONTACT_EMAIL}
		Vragen of een verzoek? Mail naar <a href={`mailto:${PRIVACY_CONTACT_EMAIL}`}>{PRIVACY_CONTACT_EMAIL}</a>.
	{:else}
		Vragen of een verzoek? Neem contact op met de beheerder van Shakka.
	{/if}
	Ben je het niet eens met hoe Shakka met je gegevens omgaat, dan kun je een klacht indienen bij de
	<a href="https://autoriteitpersoonsgegevens.nl/" target="_blank" rel="noopener noreferrer">Autoriteit Persoonsgegevens</a>.
</p>
