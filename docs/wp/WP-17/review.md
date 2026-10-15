# Review WP-17, ronde 2
Oordeel: APPROVED

Beoordeeld: `docs/wp/WP-17/blueprint.md`, revisie 2. Uitgangspunt is de review van ronde 1 (B-1 en N-1 t/m N-11).

## Blokkerend
Geen.

## Controle B-1 (ronde 1)
B-1 is echt opgelost, en de blueprint beschrijft de oplossing overal op dezelfde manier.
- **Volgorde in `WebPushNotifier.__init__`.** Eerst wordt het subject gestript en volgt de witruimte-voorcheck. Dan `Vapid.from_string(private_key=key)`, met `PRIVATE_KEY_ERROR` bij een fout. Dan `vapid.sign({"sub": subject, "aud": VAPID_PROBE_AUD})`, met `SUBJECT_ERROR` bij een fout. Beide fouten gaan via `from None`. Ontwerp, Interfaces (docstring van de constructor), A9, E3a/E3b en stap 4 zeggen hetzelfde. Stap 11 controleert met grep dat er geen eigen `re.compile` in `webpush.py` staat.
- **Proef en echte aflevering geven hetzelfde oordeel.** In py_vapid 1.9.6 roept `Vapid02.sign` `_base_sign` aan. Die doet `_check_sub`, tenzij `conf["no-strict"]` gezet is. `from_raw` maakt de instantie met `cls(key)`, dus met een lege `conf` en daarmee strikte controle. pywebpush gebruikt een meegegeven `Vapid01`-instantie ongewijzigd (`vv = vapid_private_key; vv.sign(vapid_claims)`), dus de proef draait op hetzelfde object als de echte aflevering. `https://push.example.invalid` voldoet aan de `aud`-regex `^https?://[^/:]+(:\d+)?$`. Een fout uit `sign` komt daardoor van het subject.
- **Voorbeeldsubjects nagelopen tegen de echte `_check_sub`-regex** (de mailto-tak heeft geen `$`, de https-tak wel):
  - deze falen bij constructie: `https://shakka.nl/contact` en `https://example.org/contact` (het pad wordt geweigerd door `[\w\.-]+$`), `mailto:lars@example` (het domein heeft geen punt en is geen localhost of IPv6), `lars@example.org`, `mailto:` en `http://example.org`;
  - deze zijn geldig: `mailto:test@example.org`, `https://example.org` en `https://shakka.nl`;
  - `mailto:a b@example.org` komt wel door de bibliotheek (geen `$`), maar de voorcheck van de blueprint weigert hem. De bibliotheek is hier dus niet ruimer dan de blueprint, alleen strenger. Daarom laat `test_subject_check_matches_library` dit geval terecht weg.
- **`test_subject_check_matches_library`.** De test legt het verband tussen constructie en `Vapid.sign` vast. `py_vapid.VapidException` bestaat: die is gedefinieerd in `py_vapid/__init__.py`. `main` van py_vapid is gelijk aan release 1.9.6 (de laatste commit is "Tag 1.9.6", 14 oktober 2026), dus de broncode die ik gecontroleerd heb, is de versie die geïnstalleerd wordt.
- **Sleutelfout gaat voor subjectfout.** `test_key_error_before_subject_error` sluit aan op de volgorde van de code.

## Controle van de overige revisiepunten
- **`::warning::` bij `deferred > 0`.** Dit past in het bestaande mechanisme: `StepOutcome.warnings` gaat via `build_annotations` naar `::warning::alerts: …`. De verwachte tekst in `test_hourly_deferred_warning` komt overeen met de f-string van `deferred_warning`. `escape_command_data` verandert hier niets aan. Bij `partial` blijft de exitcode 0 (`run_status` en `exit_code_for` op develop). Als het kanaal uit staat, is `deferred` altijd 0, dus de twee warnings overlappen niet.
- **`pytest.fail` in de autouse-fixture.** `Failed` is een `BaseException`. Nergens in `ingest/src` staat `except BaseException` of een kale `except:`, en `CliRunner.invoke` vangt alleen `Exception`. De bewijstest met `pytest.raises(pytest.fail.Exception)` via `send_payload` en `deliver_event` is correct. De notifier zoekt `pywebpush.webpush` pas bij de aanroep op, dus de patch werkt.
- **Re-export tegen F401.** De ruff-config selecteert `E, F, W, I, UP, B, SIM, DTZ`, dus geen `PLC0414`. De redundante alias `load_targets as load_targets` geldt in ruff als expliciete re-export. Er ontstaat geen importcyclus: `jobs.push` importeert `jobs.alerts` niet, en `jobs.runtime` importeert geen jobs.
- **pgTAP 15–19 met `user_id` A.** Elke insert heeft nu op één waarde na alleen geldige waarden. Daardoor komen de verwachte `23514` en `23505` terug, en niet `23502`. Er zijn 32 asserts in totaal (6 + 4 + 3 + 1 + 5 + 13).
- **Strippen van het subject.** `notifiers_from_settings` geeft het subject ongewijzigd door. `__init__` stript het en gebruikt het gestripte subject zowel voor de proef als voor `vapid_claims`. `secret_values` neemt het gestripte subject op. De bestaande asserts in `test_secret_values` blijven geldig, omdat er zonder subject niets bijkomt.
- **Kanaal uit en de bijwerking op `alert_state`.** Daar verandert niets aan. Zonder VAPID geeft `notifiers_from_settings` `{}`. Er volgt dan geen select op `push_subscriptions`, de state schuift door zoals in WP-10, en alleen de vooraf toegekende `id` (A3, al geaccepteerd in ronde 1) wijkt af. De nieuwe push-disabled-warning breekt geen bestaande test: alleen `test_budget_warning_on_stdout` deed een te ruime check, en die is aangepast (N-5).
- **N-2 t/m N-11.** Allemaal correct verwerkt. Daarbij komt de blueprint op geen enkel punt buiten de scope.

## Niet-blokkerend
- **N-1:** In A9 staat dat een subject dat precies `mailto:` is, als afwezig telt. Er staat niet bij of dat vóór of na `strip()` wordt vergeleken. Voorstel: `vapid_subject.strip() == "mailto:"`. Dat sluit aan op "leeg na `strip()`" en op het strippen in `__init__`.
- **N-2:** De fixture `restore_logging` in `tests/test_cli_pipeline.py` herstelt alleen `httpx` en `httpcore`. Na `configure_logging` blijft `urllib3` daardoor op `WARNING` staan voor latere tests. Dat is onschuldig, maar voor de symmetrie met `test_logsetup.py` kun je `QUIET_LOGGERS` gebruiken.
- **N-3 (aanvulling op het SSRF-punt voor WP-22):** De echte `aud` is het origin van het endpoint. Een endpoint met userinfo die een `:` bevat, of met een IPv6-host, valt buiten de `aud`-regex van `_base_sign`. Elke aflevering naar zo'n abonnement geeft dan een `VapidException`, die als niet-permanente fout telt. Dat raakt alleen de gebruiker die zo'n rij zelf invoert. Wel staat de deferred-warning dan elke run in de Actions-log. Een allowlist van push-hosts of een strengere CHECK in WP-22 lost dit mee op.
- **N-4:** `step_alerts` controleert de VAPID-configuratie pas na de stale-regel. Een configuratiefout valt dus niet op in een run waarin `alerts` om die reden `skipped` is. De run is dan al exit 1 met een `::error::`, dus dit is aanvaardbaar.

## Gecontroleerde bronnen
- https://raw.githubusercontent.com/web-push-libs/vapid/main/python/py_vapid/__init__.py (`_check_sub`, `_base_sign`, `Vapid01.__init__`, `from_string`, `from_raw`, `Vapid01.sign`, `Vapid02.sign`, `VapidException`, `Vapid = Vapid02`)
- https://github.com/web-push-libs/vapid/commits/main/python (`main` = release 1.9.6)
- https://pypi.org/pypi/py-vapid/json (1.9.6, 14 oktober 2026)
- https://raw.githubusercontent.com/web-push-libs/pywebpush/main/pywebpush/__init__.py (`isinstance(vapid_private_key, Vapid01)` → `vv.sign(vapid_claims)`, `WebPushException.status_code`, `from py_vapid import Vapid, Vapid01`)
- https://docs.astral.sh/ruff/rules/unused-import/ (redundante alias als expliciete re-export)
