# Afwijkingen WP-19

Alle afwijkingen zijn klein; geen enkele raakt een contract, schema-interface, externe API, dependency of acceptatiecriterium.

## Uit de review (verwerkt)
- **N-1.** `test_spots_sync_failure_continues` controleert nu `len(report.steps) == 7` en `all(status == "ok")` voor de stappen na `spots_sync`.
- **N-2.** RUNBOOK §8.2 noemt de uitzondering: geen grants aan `service_role` als de ingest de tabel niet nodig heeft (`sessions`, `rsvps`; verwijzing naar §16).
- **N-3.** De migratie heeft direct na `create extension` een `do`-blok dat een exception geeft als pgcrypto niet in het schema `extensions` staat. Lokaal getest: de migratie draait door.
- **N-5.** Extra asserts. `07`: plan 107 naar 112 (insert met `created_at` en met `id` als A; multi-row insert over de grens als B, 3 asserts). `08`: plan 62 naar 71 (`rsvp_update` en `rsvp_delete` op een afgelopen sessie; `get_public_session` met `null`, te korte en te lange slug; `p_seats_offered = -1`; cascade bij session-delete en bij purge met een aanbieder en een meerijder). De extra asserts staan achteraan of in een eigen blok, zodat de blueprint-nummering 1-107 en 1-62 ongewijzigd blijft.
- **N-6.** `test_no_grants_on_rsvps` matcht `TABLE` als optioneel, plus een aparte check op `grant ... on all tables`.
- **N-8.** Token alleen via POST: vastgelegd in de migratiekop en RUNBOOK §16.7.
- **N-11.** `rsvp_update` heeft na `select ... for update` op de sessie een `if not found then ... 'invalid_token'`.
- **N-12.** Beschrijving van de FK-assert in `01_schema` is "foreign keys and delete actions". Plan blijft 71.
- **N-4, N-7, N-9, N-10.** Alleen genoteerd, niet gebouwd. N-9 is wel verwerkt in RUNBOOK §16.2 (`db push` vóór de promotie naar `main`). N-4 (bovengrens `starts_at`), N-7 (melding bij `rate_limited`, moderatie-RPC in WP-22, bidi-tekens in WP-21) en N-10 (`least(p_now, now())`) blijven voor de planner van WP-20/21/22/23 open.

## Fout in de blueprint
- **E36 / assert 112 (rechtgezet in herstelronde 1, F-1).** Een eerdere versie van deze notitie stelde dat `on delete restrict` SQLSTATE `23001` geeft. Dat was onjuist: een FK met `on delete restrict` rapporteert via de RI-trigger `23503` (bevestigd door echte Postgres in CI-job `db`). De blueprint had gelijk. Assert 112 verwacht weer `23503`. Het vroegere bewijs kwam van een scratch-Postgres met een zelfgeschreven mini-pgTAP en was vals. De blueprint (E36, assert 107) noemde al `23503` en is niet aangepast.

## Overig
- Geen Docker. Als vervanging: Postgres 18 (Homebrew) als scratch-database met stubs voor `auth`, de rollen en pgcrypto, alle migraties erop, en een zelfgeschreven mini-vervanger van pgTAP (alleen lokaal, niet gecommit). `01`, `07` en `08` slaagden daarmee volledig (71, 112 en 71 asserts). Echte pgTAP kon niet worden gebouwd (compileren van externe code is geweigerd), dus de CI-job `db` blijft het definitieve bewijs; verschil in pgTAP-semantiek is het enige resterende risico. `02` en `04` zijn niet met de mini-vervanger gedraaid (ontbrekende pgTAP-functie, en een scratch-verschil in `service_role`); die bestanden zijn niet gewijzigd.
- Python-importvolgorde in `fakes.py` is door ruff gesorteerd.
- `test_migrations.py`: de purge-functie wordt gevonden via `startswith("public.purge_expired_sessions")` na de split op `create function`.
