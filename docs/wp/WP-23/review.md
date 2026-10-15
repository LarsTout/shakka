# Review WP-23, ronde 2
Oordeel: APPROVED

Ronde 2 beoordeelt revisie 2 van de blueprint. Ik heb gekeken of B-1 echt is opgelost, of N-8 klopt met de geïnstalleerde code, en of de revisie nieuwe blokkerende punten introduceert.

**B-1a (`shakka:return_to`) is opgelost. Code en tekst kloppen nu met elkaar.**
- `pruneReturnTo` gebruikt dezelfde versheidsregel als `takeReturnTo` in `web/src/lib/local-prefs.ts`. Een sleutel blijft staan als hij 0 tot en met `RETURN_TO_TTL_MS` oud is, het pad is toegestaan en de JSON geldig is. In alle andere gevallen wist `pruneReturnTo` hem. `takeReturnTo` houdt zijn huidige volgorde (lezen, altijd wissen, dan beoordelen).
- De layout roept `pruneReturnTo` aan in `onMount`. `browserStorage` is daar al geïmporteerd. Ik heb de drie scenario's nagelopen:
  - **Magic link binnen 60 minuten.** De sleutel blijft staan en `takeReturnTo` stuurt je na het inloggen terug. Dat blijft werken.
  - **Magic link na 60 minuten.** De sleutel wordt gewist. Dat verandert niets: `takeReturnTo` weigerde zo'n sleutel al.
  - **Nooit inloggen.** De sleutel wordt gewist bij de eerste start nadat hij verlopen is.
- De nieuwe zin op `/privacy` beschrijft precies dit gedrag: "gewist zodra je inlogt … gebruikt Shakka het na {RETURN_TO_TTL_MINUTES} minuten niet meer, en wist het de eerstvolgende keer dat je Shakka opent". "Hoogstens" komt niet meer voor.
- De rij in `docs/PRIVACY.md` zegt hetzelfde.
- De bestaande tests blijven groen:
  - "does nothing while signed out and keeps the key" (`layout.test.ts` r. 138, met een verse sleutel);
  - "ignores a key older than 60 minutes but removes it" (r. 131);
  - de `takeReturnTo`-tests in `local-prefs.test.ts`.
- Toets 4a matcht op de letterlijke tekst, ook na het normaliseren van witruimte.

**B-1b (GitHub) is opgelost.** Wat de uurlijkse job leest, heb ik nagekeken in de code. `jobs/alerts.py` leest `favorites` (r. 189), `alert_rules` (r. 196), `profiles` (r. 199) en `alert_state` (r. 208), en schrijft en verwijdert `alert_state`. `jobs/push.py` leest `push_subscriptions` en werkt die bij of verwijdert ze. `admin.py` is een lokale CLI en draait niet in de workflows. De zin op `/privacy`, de regel in PRIVACY.md en toetsen 4b en 4e zijn onderling consistent.

**N-8 klopt in de kern.** Ik heb het nagekeken in `.claude/worktrees/WP-21/web/node_modules`:
- **SvelteKit 3.0.1.** `constants.js` bevat `sveltekit:snapshot`, `sveltekit:navigation-snapshot`, `sveltekit:history-info` en `sveltekit:metadata`. `sveltekit:metadata` is een sleutel in `history.state`, niet in `sessionStorage`. `persist_state()` in `client.js` (r. 686-694) schrijft `HISTORY_INFO_KEY` en `SNAPSHOT_KEY`, en roept daarna `persist_navigation_snapshots` aan. Die schrijft ook `sveltekit:navigation-snapshot` (`snapshots.js` r. 74), zie N-1.
- **MapLibre 6.14.0.** In `dist/*.mjs` staat geen `caches.open` en geen `maplibre-tiles`. Een `caches`-treffer is alleen commentaar ("need larger caches", "caches previous rendered tiles"). De tekst over de HTTP-cache van de browser klopt dus. Mijn bewering uit ronde 1 over een Cache-API-tegelcache geldt niet voor deze versie.

**Kruiscontrole op modulepreload (N-3) is uitvoerbaar.** In de WP-21-build staat in `index.html` de vorm `<link href="…" rel="modulepreload">`: eerst `href`, dan `rel`. De regex van `modulepreloadFiles` is onafhankelijk van de volgorde van de attributen, en toets 7a dekt dat. `entry/payload` staat in de lijst en valt onder de startbestanden.

**Overige punten uit ronde 1:**
- **N-2:** het commentaar van het sjabloon bevat geen `{{` meer.
- **N-4:** de rekensom klopt: 300.000 bytes worden 400.000 base64-tekens, ±300.000 bytes gzip.
- **N-9:** de anker-regex werkt op alle zes de constanten. Ik heb ze gecontroleerd met `^…RETENTION: Final = timedelta`.
- **Regels in `07_sessions.test.sql`:** de regelnummers 67 en 69 kloppen met het bestand.

Er zijn geen nieuwe blokkerende punten.

## Blokkerend
Geen.

## Niet-blokkerend
N-1: De inventaris van `sessionStorage` mist één sleutel.
- **Wat:** SvelteKit 3.0.1 schrijft bij elke `persist_state()` ook `sveltekit:navigation-snapshot`. Bij Shakka is die leeg, omdat er geen `snapshot()`-registraties zijn. In de browsertabel van `docs/PRIVACY.md` staan alleen `sveltekit:history-info` en `sveltekit:snapshot`. De rij in "Externe afhankelijkheden" noemt de sleutel alleen als constante.
- **Gevolg:** geen persoonsgegevens, en `/privacy` ("scrollpositie") blijft juist. De technische inventaris is alleen niet volledig.
- **Voorstel:** zet in stap 5 dat de builder elke sleutel opneemt die kit echt naar `sessionStorage` schrijft (`grep -rn "storage.set(" node_modules/@sveltejs/kit/src/runtime/client`), dus ook `sveltekit:navigation-snapshot`. De bestaande uitwijkregel ("neem de echte namen over") dekt dit al grotendeels.

N-2: "Dit wordt gewist zodra je inlogt" geldt alleen voor inloggen in dezelfde browser.
- **Wat:** opent de mailapp de magic link in een andere browser (bijvoorbeeld een in-app-browser), dan blijft de sleutel in de oorspronkelijke browser staan. Hij wordt dan pas bij de eerstvolgende start daar gewist, als hij verlopen is.
- **Gevolg:** de volgende zin in de tekst dekt dit feitelijk af. Het is dus geen onjuiste belofte.
- **Voorstel:** schrijf eventueel "zodra je op dit apparaat inlogt".

N-3: "de eerstvolgende keer dat je Shakka opent" betekent een volledige start van de app, want `onMount` van de layout draait niet opnieuw.
- **Wat:** een PWA die uit de achtergrond terugkomt, of een tabblad dat open blijft, telt niet als "openen". In dat geval wordt de sleutel niet gebruikt maar ook niet gewist.
- **Gevolg:** A21 beschrijft dit al eerlijk. Voor de privacytekst is dit acceptabel.
- **Voorstel:** geen actie nodig.

N-4: In `local-prefs.test.ts` toets 4 staat "`removeItem` is niet aangeroepen". De bestaande fake `memory()` houdt geen aanroepen bij, dus de builder moet `removeItem` wrappen met `vi.fn` of `vi.spyOn`. Dat is triviaal, ik noem het alleen voor de volledigheid.

## Gecontroleerde bronnen
- `web/src/lib/local-prefs.ts`, `web/src/routes/+layout.svelte`, `web/test/layout.test.ts` (r. 118-143), `web/test/local-prefs.test.ts` (in de WP-23-worktree)
- `ingest/src/shakka/jobs/alerts.py`, `push.py`, `admin.py` en de `*RETENTION: Final = timedelta(...)`-constanten in `forecast.py`, `marine.py`, `tides.py`, `evaluate.py`, `alerts.py` en `sessions.py`
- `supabase/tests/07_sessions.test.sql` r. 64-70
- `.claude/worktrees/WP-21/web/node_modules/@sveltejs/kit` (versie 3.0.1): `src/runtime/client/constants.js`, `client.js` (r. 101-115, 686-694), `snapshots.js` (r. 15, 72-75), `session-storage.js`
- `.claude/worktrees/WP-21/web/node_modules/maplibre-gl` (versie 6.14.0): `dist/*.mjs` en `dist/maplibre-gl.d.ts` (zoekterm `caches.open|maplibre-tiles|caches`)
- `.claude/worktrees/WP-21/web/build/index.html` (modulepreload-links, volgorde van attributen) en de static imports in `entry/start`, `entry/app` en `nodes/0`
- Externe documentatie: in ronde 1 gecontroleerd en ongewijzigd gebruikt (zie de bronnen van ronde 1: Cloudflare `_headers`, de CSP-optie van SvelteKit, Supabase-auditlogs en -pricing, de Supabase-changelog van april 2025, axe-core, CSP-directives van MapLibre)
