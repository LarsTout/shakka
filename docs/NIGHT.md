# Nachtrun 14 oktober 2026

Vier WP's parallel gebouwd op eigen branches, afgetakt van `develop` (met WP-00 en WP-01). Geen PR's, geen merges. Elke branch staat gepusht met CI groen (`ingest`, `db`, en voor WP-13 ook `web`). Alle vier eindigen op `NEEDS_LARS` voor precies één acceptatiecriterium dat de lokale Supabase-stack (Docker) of jouw accounts nodig heeft; vanuit de sandbox is Docker niet bereikbaar. Alle andere criteria zijn PASS.

| WP | Branch | Blueprint | Build | Verificatie | Wacht op jou |
|---|---|---|---|---|---|
| WP-02 Spotprofielen | `wp/WP-02` | approved r2 | 324 tests | AC-1..5,7 PASS | AC-6: `spots sync` tegen lokale stack |
| WP-03 Wind-ingest | `wp/WP-03` | approved r2 | 382 tests | AC-1..7 PASS | AC-8: twee echte runs, RUNBOOK §9 |
| WP-04 Getij-ingest | `wp/WP-04` | approved r1 | 293 tests | AC-1..4 PASS | AC-5: `tides fetch` tegen lokale stack |
| WP-13 PWA-basis | `wp/WP-13` | approved r1 | 87 web + 202 ingest | AC-1..6 PASS | AC-7: Cloudflare Pages, Supabase Auth-URLs, magic-link-test |

Per WP: `docs/wp/WP-XX/{blueprint,review,deviations,verification}.md` op de branch. De exacte commando's voor jouw stap staan in `verification.md`.

## Beslissingen die ik namens jou heb genomen (bevestigen of terugdraaien)

1. **WP-03, vlagen (A14):** Open-Meteo levert `wind_gusts_10m` als maximum over het *vorige* uur. Gekozen: een uur terugschuiven, zodat `gust_kn` op `valid_at=T` het maximum over [T, T+1h) is, consistent met de projectafspraak. Laatste uur krijgt `None`. Terugdraaien: R10 in de blueprint. **Bevestig dit vóór WP-05.**
2. **WP-03, `cell_selection=sea`:** standaard rasterpunt lag bij Wijk aan Zee 7 km landinwaarts (11 kn vs 18 kn). Voorstel planner overgenomen.
3. **WP-04, `httpx` i.p.v. `ddlpy`:** `ddlpy` 0.10.0 doet requests zonder timeout en trekt pandas/numpy binnen. Reviewer heeft het nagekeken. Nee zeggen = binnenkant van twee functies (R2). Daarna de stackregel in PROJECT_PLAN/WORK_PACKAGES aanpassen.
4. **WP-04, agger:** "kind wisselt af" toegestaan met uitzondering `laagwater 1` → `laagwater 2`. Gevolg voor WP-05: getijvoorkeur op geschat niveau, niet op strikte afwisseling.
5. **WP-13, SvelteKit 3** (uit 1 okt 2026) i.p.v. 2. Reviewer heeft elke aanname tegen de kit-3-docs geverifieerd; builder bevestigt dat beide onzekerheden goed uitvielen. Gevolg: `#lib`, `$app/env/public`, `src/service-worker/index.ts`, config in `vite.config.ts`. Regels 891, 899 en 1101 in WORK_PACKAGES moeten mee (review N-1).
6. **WP-13, `shouldCreateUser: false`:** geen rijen van onbekende e-mailadressen in `auth.users`/`profiles` tot WP-22. Gevolg: jij maakt jezelf eenmalig aan in het Dashboard (RUNBOOK 9.2).
7. **WP-13, Node 24.22.0** (Cloudflare: `NODE_VERSION=24.22.0`), placeholder-icoon.
8. Kleine reviewpunten die de builders hebben overgenomen staan per WP in `deviations.md`.

## Jouw stappen morgen

1. `supabase db push` voor WP-01 (nog niet gedaan; migraties staan op `develop`).
2. Per WP de `NEEDS_LARS`-stap uit `verification.md` draaien met `supabase start` lokaal.
3. Beslissingen 1–7 hierboven bevestigen of terugdraaien.
4. Per branch: `gh pr create --base develop --head wp/WP-XX`, of eerst in een nieuwe sessie `/ship WP-XX` laten hervatten vanaf `verifying` zodat de verifier opnieuw draait en STATUS op `done` komt.
5. Mergen in deze volgorde om RUNBOOK-conflicten klein te houden: WP-02, WP-03, WP-04, WP-13. WP-03 en WP-04 voegen allebei een "sectie 9" aan RUNBOOK toe en wijzigen `cli.py`; de tweede merge moet hernummeren.

## Daarna startbaar

- WP-06 (na WP-02), WP-05 (na WP-02, 03, 04).
- Nog niet startbaar: WP-07+ (na WP-05), WP-14 (na WP-10, 12, 13).

## Verbruik

16 subagent-runs: 4 planners (+2 revisies), 6 reviews, 4 builders, 4 verifiers. Circa 2,0M subagent-tokens, ~2,5 uur wandkloktijd.
