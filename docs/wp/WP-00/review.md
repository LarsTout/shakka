# Review WP-00, ronde 1
Oordeel: APPROVED

## Blokkerend
Geen.

Toetsing samengevat:
- **Plan en scope:** AC-1 t/m AC-9 hebben elk een concrete test of een handmatige controle met een `NEEDS_LARS`-uitweg. De blueprint bouwt niets uit WP-01 (schema, `shakka.db`, CI-job `db`), WP-11 (cron) of WP-13 (`/web`). Bij de extra's (`shakka.doctor` als aparte module, `--version`, `test_repo_hygiene.py`) staat steeds een reden en ze vallen binnen het doel.
- **Randvoorwaarden:** er zijn geen betaalde diensten. CI draait zonder secrets en werkt dus ook voor fork-PR's in de publieke repo. Secrets zijn `SecretStr`. Doctor toont geen waarden, geen URL, geen body en geen exceptionmelding. De grep-check draait ook in pytest en dus in CI. Open-Meteo, scraping, offshore en bronvermelding spelen in deze WP niet.
- **Contracten:** de velden van `Settings`, `get_settings() -> Settings` en `make_client(*, timeout: float = 30.0) -> httpx.Client` zijn exact gelijk aan WORK_PACKAGES. De genormaliseerde `supabase_url` (zonder trailing slash) past bij `SupabaseRest(url, secret_key)` uit WP-01. Omdat `tests/` geen `__init__.py` krijgt en pytest de standaard import-mode houdt, werkt `from fakes import FakeSupabase` (WP-01). Doordat `httpx.Client(` alleen in `src/shakka/http.py` staat, is WP-22 AC-1 voorbereid.
- **Externe API's en packages:** de versies en de SHA-pin heb ik zelf gecontroleerd (zie bronnen). Ik vond geen niet-bestaande parameters.
- **Domeinlogica:** in deze WP alleen de puurheidschecker. De resolutie van relatieve imports (`from .. import db` vanuit `shakka.domain.probe` wordt `shakka.db`) en de allowlist kloppen met "Code-indeling". `REPO_ROOT = parents[3]` klopt voor `ingest/src/shakka/config.py`. In een worktree wijst dit naar de worktree-root, waar `/ship` `.env` als symlink neerzet, en `is_file()` volgt die symlink.

## Niet-blokkerend
N-1: Het doctor-gedrag voor `SUPABASE_PUBLISHABLE_KEY` is niet vastgelegd voor het geval dat Settings niet laden (bijv. secret ontbreekt, publishable wel gezet). Waar: Interfaces, `shakka.doctor`, uitvoertabel. De tabel zegt "`ok` alleen als settings geladen zijn", maar niet of er dan `unset`, niets of iets anders verschijnt. `test_doctor_partial_env_does_not_leak_values` raakt precies dit geval. Voorstel: leg één regel vast, bijv. "laden de settings niet, dan geen publishable-regel en geen prefix-waarschuwingen".

N-2: Edge case E1 (een `.env` gekopieerd uit `.env.example`, met lege waarden) wordt alleen getest via een lege OS-variabele (`test_doctor_empty_string_counts_as_missing`), niet via een dotenv-bestand. Voorstel: voeg een test toe met een tmp-`.env` met `SUPABASE_URL=` en `SUPABASE_SECRET_KEY=` die `missing` voor beide verwacht. Zo is aangetoond dat `env_ignore_empty` ook voor de dotenv-bron geldt. De pydantic-settings-documentatie zegt dat niet expliciet.

N-3: De puurheidschecker meldt alleen calls op `.now`/`.today`. Een verwijzing zonder call, zoals `Field(default_factory=datetime.now)`, glipt erdoor. Dat is in pydantic-modellen een realistisch patroon. Hetzelfde geldt voor `builtins.open(...)` (`builtins` is stdlib en niet verboden). Het contract (tekst `.now(`) eist dit niet, maar de bedoeling ("domein roept nooit `datetime.now()` aan") wel. Voorstel: meld elke `ast.Attribute` met `attr` in {`now`, `today`, `utcnow`}, ook zonder call. Voeg `builtins` toe aan de verboden modules, of meld een attribuut-call `open`. Neem beide gevallen op in `test_checker_flags`.

N-4: Doctor vangt alleen `httpx.HTTPError`. `httpx.InvalidURL` en bijv. een `UnicodeEncodeError` (bij een niet-ASCII-teken in de key-header) erven daar niet van en geven een traceback. Die bevat dan een exceptionmelding, wat E10 en de docstring uitsluiten. Voorstel: vang als laatste een brede `Exception`, toon alleen `type(exc).__name__` en geef exit 1.

N-5: Bij `_validate_supabase_url` is "host" niet eenduidig. Voorstel: toets op `urlsplit(...).hostname`, zodat `http://[::1]:54321` werkt. Weiger userinfo (`https://user:pass@…`), omdat die anders via `netloc` in de genormaliseerde URL blijft staan.

N-6: Commitconventie. De blueprint schrijft `chore(ingest): …`, `feat(ingest): …` enz. voor, maar `.claude/agents/builder.md` zegt `WP-XX: <wat>`. Voorstel: kies er één, bijv. `WP-00: feat(ingest): …`, zodat de builder niet zelf hoeft te kiezen.

N-7: In de `/ship`-flow wordt pas in stap 5 gepusht, na de verificatie. De verifier zal AC-6 (groene CI-run) daardoor bijna zeker als `NEEDS_LARS` melden, en dan stopt de orchestrator. Voorstel: noem in het stappenplan expliciet dat de groene run op de PR (`gh pr checks`) AC-6 afdekt. Of laat de verifier AC-6 statisch toetsen (`test_ci_workflow_contract`) met de PR-checks als bevestiging.

N-8: De User-Agent bevat `github.com/LarsTout/shakka` en daarmee Lars' GitHub-handle. Het is de publieke project-URL en geen gebruikersdata, dus dit past bij "zonder persoonsgegevens van gebruikers". Toch even laten bevestigen door Lars.

N-9: Worktrees komen onder `.claude/worktrees/` in de repo-root. Die map staat niet in `.gitignore` en verschijnt dus als untracked in de hoofdcheckout. Voorstel: neem `.claude/worktrees/` op in de `.gitignore`-wijziging. Kleine moeite, en het past bij de repo-hygiëne van deze WP.

N-10: `actions/checkout@v7` staat op een tag, `setup-uv` op een SHA. Dat is in orde, maar het is inconsistent. Overweeg beide op een SHA te pinnen.

N-11: Laat ten minste de AC-4-test (`test_doctor_empty_env_reports_missing`) via `CliRunner().invoke(cli, ["doctor"])` lopen in plaats van `run_doctor` direct aan te roepen. Dan zijn de click-koppeling en de omzetting van `SystemExit` naar de exitcode ook aantoonbaar gedekt.

## Gecontroleerde bronnen
- https://pypi.org/pypi/pydantic-settings/json (2.16.0, uitgebracht op 14-10-2026; vereist python-dotenv)
- https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/ (`env_ignore_empty`, standaard `extra='forbid'` ook voor dotenv, `_env_file=None`, env gaat vóór dotenv)
- https://pypi.org/pypi/click/json (8.5.0)
- https://pypi.org/pypi/httpx/json (0.28.1, geen 0.29)
- https://pypi.org/pypi/pytest/json (9.1.1)
- https://pypi.org/pypi/ruff/json (0.17.0)
- https://pypi.org/pypi/uv-build/json (0.13.1)
- https://github.com/astral-sh/setup-uv en https://github.com/astral-sh/setup-uv/releases (v10.3.0 = `1c37ad07a6a961277cf70c0d37d6f313000f5884`; input `working-directory` leest `.python-version`; `enable-cache` standaard `auto`)
- https://github.com/actions/checkout (README gebruikt `@v7`)
- https://supabase.com/docs/guides/api/api-keys (`apikey`-header, geen Bearer; 401 voor een secret key bij een browser-User-Agent; legacy-sleutels vervallen eind 2026; het gedrag van de `/rest/v1/`-root staat er niet in, zoals de blueprint ook zegt)
- https://supabase.com/docs/reference/cli/supabase-init (standaard niet-interactief, `-i`, `--force`)
- https://git-scm.com/docs/git-grep (`--untracked` respecteert `.gitignore`, tenzij `--no-exclude-standard` is gezet)
