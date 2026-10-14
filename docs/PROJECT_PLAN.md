# Projectplan: Shakka, gratis versie

> Dit document is de bron van waarheid voor het bouwen van de app. Agents lezen dit eerst. Wijzigingen in scope gaan via Lars.

## 1. Doel

Een gratis app die het leven van een Nederlandse kiter makkelijker maakt. Kernvraag die de app beantwoordt:

**"Gaat het waaien op mijn spot, mag ik daar kiten, en wie gaat er mee?"**

Geen ads, geen abonnementen, geen verdienmodel. Eerste gebruiker is Lars zelf, daarna zijn kitecrew, daarna de Nederlandse community.

### Wat de app onderscheidt
Losse features bestaan al (Windmaster, KiteGids, Hanglos, Windy.app). Het onderscheid zit in de combinatie:

1. Een **oordeel per spot** in plaats van ruwe data: rijdbaar ja/nee per uur, met offshore-vlag, seizoenssluiting, getij en vlagerigheid meegewogen.
2. **Alerts die standaard goed staan** (defaults uit het spotprofiel) en die je kunt verfijnen.
3. **"Ik ga"**: een alert wordt met één tik een sessie, die je als link in WhatsApp deelt. Vrienden zien wie er gaat en tikken "ik ook" zonder account of app.

### Non-goals (niet bouwen)
Eigen weermodel, session tracking, open carpoolmarkt tussen vreemden, gear-marktplaats, waardebepaling, betalingen, native apps (v1 is een PWA), ads, analytics van derden.

## 2. Harde randvoorwaarden

| Randvoorwaarde | Gevolg voor het ontwerp |
|---|---|
| **€0 per maand** hosting | Alleen gratis tiers. Kosten moeten schalen met aantal spots, niet met aantal gebruikers. |
| **Open-Meteo free tier** (niet-commercieel, max 10.000 calls/dag, 300.000/maand) | Forecasts worden server-side per spot opgehaald en gecachet. Clients roepen Open-Meteo nooit direct aan. Budgetbewaking in de ingest-job. |
| **CC BY 4.0** (Open-Meteo, KNMI) | Bronvermelding zichtbaar in de app (footer en spotpagina). |
| **Supabase free** (500 MB, pauzeert na 7 dagen inactiviteit) | Oude forecastdata wordt opgeruimd (bewaar max 48 uur historie). De uurlijkse job houdt het project actief. |
| **MapTiler free** (5.000 map sessions/maand, niet-commercieel) | Kaart lazy laden. Lijstweergave als fallback. |
| **Geen scraping** van Windguru, Windfinder, KiteGids, Hanglos of Marktplaats | Spotdata wordt handmatig samengesteld en door Lars geverifieerd. |
| **Privacy** | Minimale persoonsgegevens: e-mail voor login, optioneel een voornaam bij RSVP. Geen locatietracking. |

## 3. Architectuur

```
GitHub Actions (cron, elk uur)
  └─ ingest (Python)
       ├─ Open-Meteo forecast (meerdere modellen) ─┐
       ├─ Open-Meteo marine (golven)                ├─► Supabase Postgres
       ├─ Rijkswaterstaat (getijden, 1x per dag)    │     ├─ spots, forecasts, tides
       ├─ evaluatie per spot per uur ───────────────┤     ├─ evaluations
       └─ alert engine ──► Web Push / Telegram      │     └─ users, rules, sessions
                                                    │
Cloudflare Pages: PWA (SvelteKit, static) ◄─────────┘ (supabase-js + RLS)
  ├─ kaart (MapLibre + MapTiler)
  ├─ spotpagina met uuroordeel
  ├─ favorieten en alertinstellingen
  └─ /s/{slug}: publieke sessiepagina (werkt zonder account)
```

### Stack

| Laag | Keuze | Waarom |
|---|---|---|
| Ingest en logica | Python 3.12, `uv`, `httpx`, `pydantic`, `astral` (zon op/onder), `ddlpy` (Rijkswaterstaat), `pywebpush` | Lars is Python-native. Alle domeinlogica zit hier, goed testbaar. |
| Scheduler | GitHub Actions cron (elk uur) | Gratis, geen server. |
| Database en auth | Supabase (Postgres, magic link login, Row Level Security) | Gratis tier ruim genoeg. |
| Frontend | SvelteKit met static adapter, TypeScript, PWA (manifest + service worker) | Licht, snel, geen server nodig. |
| Hosting frontend | Cloudflare Pages | Gratis. |
| Kaart | MapLibre GL + MapTiler tiles | Gratis tier. |
| Notificaties | Web Push (VAPID) als hoofdkanaal, Telegram-bot als kanaal voor M1 | Allebei gratis. |

### Repo-structuur

```
/ingest          Python package: clients, evaluatie, alerts, notificaties
/ingest/tests
/data/spots.yaml Handmatig samengestelde spotprofielen
/supabase        Migraties, RLS-policies, seed
/web             SvelteKit PWA
/docs            Plan, work packages, blueprints, reviews, status
/.github/workflows
```

## 4. Domeinmodel (kern)

### Spotprofiel (`data/spots.yaml`)
Het spotprofiel is de waardevolste data van de app. Velden:

| Veld | Betekenis |
|---|---|
| `id`, `name`, `lat`, `lon`, `region` | Identiteit en locatie |
| `shore_normal_deg` | Richting loodrecht op de kustlijn, van land naar water. Hieruit wordt per windrichting afgeleid of het onshore, side-on, side-shore of offshore is. |
| `ridable_dirs` | Optionele expliciete override van rijdbare richtingen (bijv. voor meren en dijken waar de kustlijnregel niet volstaat) |
| `hazards` | Vrije tekst: stroming, ondiepten, obstakels |
| `tide_sensitive` | `none`, `prefer_low`, `prefer_high`, `avoid_low` plus optioneel een minimumwaterstand |
| `rws_station` | Dichtstbijzijnde Rijkswaterstaat-getijstation |
| `season` | Periodes waarin kiten niet is toegestaan |
| `status` | `allowed`, `limited`, `forbidden` |
| `level` | `beginner`, `intermediate`, `advanced` |
| `default_min_kn` | Standaard ondergrens voor alerts |
| `notes` | Parkeren, opstapplek, drukte |
| `verified` | `false` tot Lars het profiel heeft gecheckt tegen de NKV spotkaart en lokale regels |

Startset (circa 25 spots): Wijk aan Zee, IJmuiden, Zandvoort, Bloemendaal, Noordwijk, Langevelderslag, Katwijk, Scheveningen, Kijkduin, Oostvoorne, Brouwersdam, Neeltje Jans, Vrouwenpolder, Domburg, Workum, Makkum, Hindeloopen, Lemmer, Den Helder, Callantsoog, Petten, Camperduin, Schellinkhout, Muiderberg, Lauwersmeer. Agents vullen geen feitelijke waarden in die ze niet zeker weten: onzekere velden blijven leeg en `verified: false`.

### Evaluatie per spot per uur
Uitkomst per uur: `go`, `marginal`, `no_go`, plus redenen. Regels:

- Windkracht binnen bereik van de rider (min/max knopen).
- Vlagerigheid: verschil of ratio tussen vlaag en gemiddelde.
- Richtingsklasse uit `shore_normal_deg`: **offshore en side-offshore zijn altijd `no_go`** met expliciete waarschuwing. Niet overschrijfbaar.
- Alleen daglicht (zonsopkomst tot zonsondergang, met marge).
- Seizoenssluiting of `status: forbidden` geeft `no_go`.
- Getij-voorkeur van de spot.
- Modelonzekerheid: spreiding tussen modellen (KNMI Harmonie, ICON, ECMWF, GFS) bepaalt een betrouwbaarheidsscore. Grote spreiding geeft hooguit `marginal`.

### Alerts
- Een alertregel = defaults van het spotprofiel, overschreven met wat de gebruiker instelt: min/max knopen, toegestane richtingsklassen, tijdvenster (bijv. alleen weekend of na 17:00), minimaal aantal aaneengesloten `go`-uren, dagen vooruit.
- Alert gaat af op een **window** (aaneengesloten uren), niet op een los uur.
- **Deduplicatie**: één melding per window. Nieuwe melding alleen bij een wezenlijke verandering (beter, slechter, of geannuleerd). Status wordt bijgehouden per gebruiker, spot en window.
- Bericht bevat: spot, tijdvenster, wind en richting, richtingsklasse, getij indien relevant, kite-advies, betrouwbaarheid, en een knop "ik ga".

### Kite-advies
Op basis van gewicht, niveau en quiver van de gebruiker en de windkracht per uur. Advies is altijd een maat uit de eigen quiver. Formule en tabellen worden vastgelegd in de blueprint en getest tegen een set handmatig gecontroleerde voorbeelden.

### Sessies ("ik ga")
- Een sessie = spot + datum + tijdvenster + organisator + optioneel aantal vrije plekken in de auto en een vertrekpunt.
- Publieke link `/s/{slug}` met actuele forecast, oordeel en lijst van wie er gaat.
- RSVP zonder account: alleen een voornaam. Rate limiting en een geheime edit-token per RSVP in plaats van een account.
- Carpool is een veld binnen de sessie (plekken vrij, wie rijdt met wie mee), geen aparte markt. Kosten delen gebeurt buiten de app (Tikkie-link optioneel).

## 5. Work packages

Volgorde en afhankelijkheden. Elke WP doorloopt de pijplijn uit sectie 6.

| WP | Naam | Afhankelijk van | Mijlpaal |
|---|---|---|---|
| WP-00 | Repo, tooling, CI, Supabase-project, secrets | | M1 |
| WP-01 | Datamodel en migraties (spots, forecasts, tides, evaluations, users, rules, alert_state, push_subscriptions, sessions, rsvps) inclusief RLS | WP-00 | M1 |
| WP-02 | Spotprofielen: schema, validatie, seed-loader, startset met `verified: false` | WP-01 | M1 |
| WP-03 | Forecast-ingest: Open-Meteo multi-model + marine, normalisatie naar knopen, opslag, opruimen, call-budget | WP-01 | M1 |
| WP-04 | Getij-ingest: Rijkswaterstaat astronomisch getij per station, hoog/laagwater | WP-01 | M1 |
| WP-05 | Evaluatie-engine (puur Python, zonder I/O) | WP-02, WP-03, WP-04 | M1 |
| WP-06 | Kite-advies | WP-05 | M1 |
| WP-07 | Alert-engine: regels, windows, deduplicatie, berichtopbouw | WP-05, WP-06 | M1 |
| WP-08 | Notificaties: Telegram-kanaal (M1), daarna Web Push (M2) | WP-07 | M1/M2 |
| WP-09 | Orchestratie: GitHub Actions workflow die alles elk uur draait, logging, foutmeldingen naar Lars | WP-03 t/m WP-08 | M1 |
| WP-10 | PWA-basis: SvelteKit, auth (magic link), layout, bronvermelding, installeerbaar | WP-01 | M2 |
| WP-11 | Kaart en spotpagina met uuroordeel en redenen | WP-10, WP-05 | M2 |
| WP-12 | Favorieten, profiel (gewicht, niveau, quiver) en alertinstellingen | WP-10, WP-07 | M2 |
| WP-13 | Web Push in de PWA (subscribe, service worker, ontvangen) | WP-08, WP-10 | M2 |
| WP-14 | Sessies: aanmaken vanuit alert of spotpagina, publieke pagina `/s/{slug}`, RSVP zonder account, carpoolvelden, WhatsApp-share | WP-11, WP-12 | M3 |
| WP-15 | Hardening: rate limits, foutafhandeling, privacy-check, toegankelijkheid, performance, kostenbewaking | alles | M4 |

### Mijlpalen
- **M1, "werkt voor mij"**: Lars krijgt correcte Telegram-alerts voor zijn favoriete spots. Geen UI nodig.
- **M2, "PWA"**: kaart, spotoordeel, eigen alertinstellingen, push op telefoon.
- **M3, "crew"**: "ik ga"-links in WhatsApp, RSVP zonder account, carpoolplekken.
- **M4, "klaar voor anderen"**: hardening, daarna delen met kitevrienden en een studentenclub.

Na elke mijlpaal: Lars test een week zelf. Pas door naar de volgende als de vorige echt gebruikt wordt.

## 6. Werkwijze voor Claude Code

Elke work package doorloopt vijf stappen. Elke stap draait in een eigen subagent met een eigen context, zodat de hoofdsessie schoon blijft en de controle echt onafhankelijk is.

| Stap | Agent | Model | Effort | Tools | Input | Output |
|---|---|---|---|---|---|---|
| 0. Opdelen (eenmalig) | `architect` | fable (of opus) | high | lezen, schrijven in `/docs` | Dit plan | `docs/WORK_PACKAGES.md` met per WP scope, interfaces, acceptatiecriteria; `docs/STATUS.md` |
| 1. Blueprint | `planner` | opus | high | lezen, schrijven in `/docs/wp/WP-XX/` | Plan, WP-sectie, blueprints van afhankelijkheden | `blueprint.md` |
| 2. Onafhankelijke review | `reviewer` | fable (of opus) | high | alleen lezen, schrijven van één reviewbestand | Plan, WP-sectie, blueprint. **Niet** de redenering van de planner. | `review.md` met oordeel `APPROVED` of `CHANGES_REQUIRED` |
| 3. Bouwen | `builder` | sonnet | medium | alles, in een git worktree | Goedgekeurde blueprint | Code + tests, één commit per logisch stuk |
| 4. Verificatie | `verifier` | sonnet | high | lezen, tests draaien, geen edits | Blueprint, acceptatiecriteria, diff | `verification.md` met pass/fail per criterium |

Mechanisch werk (formatteren, lint fixen, seed-YAML valideren) mag naar `haiku`.

### Regels per stap
- **Blueprint** bevat: doel, bestanden die worden aangemaakt of gewijzigd, publieke interfaces en datacontracten, edge cases, testplan (welke tests, welke fixtures), risico's, en expliciet wat buiten scope valt.
- **Review** checkt: past het bij het plan en de randvoorwaarden, zijn de acceptatiecriteria toetsbaar, kloppen de interfaces met afhankelijke WP's, missen er edge cases, wordt er iets gebouwd dat een non-goal is, zijn er kosten- of licentierisico's. Blokkerende punten genummerd. Maximaal 2 review-rondes, daarna beslist Lars.
- **Bouwen** volgt alleen een blueprint met status `APPROVED`. Afwijken mag niet stilzwijgend: de builder schrijft een afwijking op in `deviations.md` en stopt als die het ontwerp raakt. Tests eerst voor alle domeinlogica.
- **Verificatie** draait de volledige testsuite, toetst elk acceptatiecriterium, en checkt de randvoorwaarden uit sectie 2. Bij falen terug naar de builder, maximaal 2 keer, daarna naar Lars.
- **Status** van elke WP staat in `docs/STATUS.md`: `todo`, `blueprint`, `in_review`, `approved`, `building`, `verifying`, `done`, `blocked`. Een nieuwe sessie leest eerst dit bestand.

### Context-hygiëne
- `CLAUDE.md` blijft kort: projectdoel in twee zinnen, stack, commando's (test, lint, run), en de harde randvoorwaarden. Details staan in dit plan.
- Agents krijgen alleen de documenten die hun stap nodig heeft, niet de hele repo.
- Eén work package per sessie. Na `done` een nieuwe sessie (of `/clear`) starten.

### Momenten waarop Lars beslist
1. Na stap 0: work packages goedkeuren.
2. Na `CHANGES_REQUIRED` twee keer achter elkaar.
3. Bij een `deviations.md` die het ontwerp raakt.
4. Spotdata: elk spotprofiel wordt door Lars op `verified: true` gezet.
5. Na elke mijlpaal: zelf een week testen.

## 7. Definition of done per work package
- Alle acceptatiecriteria uit `WORK_PACKAGES.md` aantoonbaar gehaald in `verification.md`.
- Tests groen in CI.
- Geen nieuwe betaalde dienst, geen client-side calls naar Open-Meteo, bronvermelding intact.
- `docs/STATUS.md` bijgewerkt.

## 8. Open punten
- Open-Meteo per mail bevestigen dat een gratis publieke app zonder ads onder niet-commercieel valt (vóór M4).
- Spotprofielen verifiëren tegen NKV spotkaart en gemeentelijke regels; mogelijk de NKV benaderen voor een datapartnerschap.
