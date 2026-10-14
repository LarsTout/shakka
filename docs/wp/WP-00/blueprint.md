# Blueprint WP-00: Repo, tooling, CI en Supabase-koppeling
Status: APPROVED
Revisie: 1

## Doel
Een repo-basis waarin elke volgende WP meteen kan testen, linten en (lokaal) met Supabase kan werken. Vanaf dag één afgedwongen:
- de puurheidsregel voor `shakka.domain` (AST-test);
- secret-hygiëne (`.env.example` zonder waarden, grep-check op sleutels, `doctor` lekt nooit waarden).

Na deze WP bestaan `ingest/` als uv-project met het package `shakka`, de modules `shakka.config`, `shakka.http`, `shakka.cli` (met `shakka doctor`), een lege `shakka.domain`, CI voor de ingest, `supabase/config.toml` en `docs/RUNBOOK.md`.

## Aannames
- A1. `.env` staat in de repo-root (`/Users/larst/Dev/Shakka/.env`, gitignored). Alle `uv run`-commando's draaien vanuit `ingest/`. `shakka.config` vindt `.env` via een pad relatief aan het package, niet via de cwd.
- A2. Lars' `.env` gebruikt de nieuwe namen (`SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`). De oude `.env.example` had nog `SUPABASE_ANON_KEY` en `SUPABASE_SERVICE_ROLE_KEY`; die namen worden niet meer gelezen. Staat er nog een oude naam in `.env`, dan wordt die genegeerd en meldt `doctor` de nieuwe naam als `missing`. Dan is AC-5 `NEEDS_LARS`.
- A3. `GET {SUPABASE_URL}/rest/v1/` met header `apikey: <sb_secret_…>` geeft 2xx op Lars' project. Zo staat het in WORK_PACKAGES.md (gecontroleerd op 14 oktober 2026). Dat de root met een publishable key 401 geeft, staat niet in de publieke documentatie (zie Risico's R1).
- A4. De builder heeft de Supabase CLI (`supabase`) of `npx`, zodat hij `supabase init` kan draaien. Docker is voor deze WP niet nodig.
- A5. De builder pusht `wp/WP-00` alleen naar `origin` als de orchestrator of Lars dat uitdrukkelijk toestaat. Anders controleert Lars AC-6 (`NEEDS_LARS`).
- A6. De ingest draait op Python 3.12 (randvoorwaarde uit CLAUDE.md). uv haalt 3.12 zelf op als die lokaal ontbreekt.

## Ontwerp

**Projectlayout.** `ingest/` is een uv-project met src-layout en build-backend `uv_build`. Het package heet `shakka` (`ingest/src/shakka/`). Het console-script `shakka` wijst naar `shakka.cli:main`. `uv sync` installeert het project editable, dus `Path(__file__)` in `shakka/config.py` wijst naar de bron in de repo. Daaruit volgt `REPO_ROOT` (`parents[3]`). Een test bewaakt dat `REPO_ROOT / "ingest" / "pyproject.toml"` bestaat, zodat een verkeerde root meteen opvalt. `uv.lock` wordt gecommit. CI draait met `UV_LOCKED=1`, zodat een verouderde lockfile faalt terwijl de commando's letterlijk die van AC-1 en AC-2 blijven.

**Configuratie.** `shakka.config.Settings` is een `pydantic_settings.BaseSettings` met precies de velden uit het contract. Keuzes:
- `env_ignore_empty=True`: een gekopieerde `.env.example` met `SUPABASE_SECRET_KEY=` telt als ontbrekend, niet als lege string.
- `extra="ignore"`: de standaard is `forbid`, en dan zou elke onbekende sleutel in `.env` (oude namen, `PUBLIC_*`) een crash geven.
- OS-omgeving gaat vóór `.env`. Dat is het standaardgedrag van pydantic-settings, en zo werkt GitHub Actions met secrets als env.
- `get_settings()` leest de modulevariabele `ENV_FILE` pas bij aanroep en geeft `_env_file=None` mee als het bestand niet bestaat. Tests kunnen `ENV_FILE` zo omleiden, en het gedrag bij een ontbrekend bestand hangt niet af van een ongedocumenteerd detail van pydantic-settings.
- `supabase_url` krijgt een validator: alleen `https://`, of `http://` naar `localhost`/`127.0.0.1`/`::1` (voor de lokale stack op `http://127.0.0.1:54321`). Geen pad, query of fragment, en een eventuele trailing slash gaat eraf. Zo gaat de secret key nooit in cleartext naar een remote host, en wordt een geplakte REST-URL (`…/rest/v1`) meteen herkend.
- Secrets zijn `SecretStr`, dus `repr(settings)` toont ze niet.

**HTTP.** `shakka.http.make_client(*, timeout=30.0)` geeft een `httpx.Client` met:
- `httpx.Timeout(timeout)` (connect, read, write en pool gelijk);
- `follow_redirects=False`, zodat de `apikey`-header nooit via een redirect naar een andere host gaat;
- User-Agent `shakka-ingest/<versie> (+https://github.com/LarsTout/shakka)`. Daarin staat geen e-mail of naam van een gebruiker, alleen de publieke project-URL, zodat API-aanbieders weten wie belt. De UA bevat geen `Mozilla`: Supabase weigert secret keys bij een browser-achtige User-Agent met 401.

Een timeout die niet positief en eindig is, geeft `ValueError`. De signature blijft exact zoals in het contract. Tests vervangen de fabriek via monkeypatch en geven geen transport-parameter mee.

**CLI.** Gekozen is `click` (8.x), niet `argparse` of `typer`:
- latere WP's hebben geneste groepen nodig (`spots validate`, `admin rule set`, …);
- `click.testing.CliRunner` maakt CLI-tests eenvoudig;
- `typer` voegt `rich` toe en geeft help-uitvoer die op terminalbreedte wraps, wat tests broos maakt.

`shakka.cli` bevat alleen de root-groep `cli`, `main()` en de command-registratie. De logica van `doctor` staat in `shakka.doctor.run_doctor()`, apart te testen. Conventie voor latere WP's: elke WP voegt in `shakka/cli.py` een `@cli.group()` of `@cli.command()` toe en importeert zware modules (httpx-clients, ddlpy, yaml) pas binnen de commandfunctie. Zo blijft `shakka --help` snel en zonder side effects.

**Doctor.** `run_doctor` doorloopt deze stappen:
1. Settings laden. Een `ValidationError` wordt omgezet naar regels `missing NAAM` of `invalid NAAM`, via `exc.errors(include_input=False, include_url=False, include_context=False)` en `loc[0].upper()`. De waarde of de pydantic-melding wordt nooit geprint.
2. Prefix-waarschuwingen (`sb_secret_`, `sb_publishable_`). Die veranderen de exitcode niet, omdat de lokale stack of een legacy-sleutel nog kan werken.
3. Precies één `GET {supabase_url}/rest/v1/` met alleen de header `apikey: <secret>`, zonder `Authorization` (Supabase: nieuwe sleutels op `apikey`, niet als Bearer). Timeout 10 s.
4. Statuscode duiden met vaste teksten.

De uitvoer bevat nooit een waarde van een variabele, ook niet de URL, en nooit de response body of een exceptionmelding van httpx (alleen de klassenaam). Exitcode 0 alleen als de configuratie compleet is en de request 2xx gaf, anders 1.

**Puurheidstest.** `ingest/tests/test_domain_purity.py` bevat de checker zelf (functie `check_source`) en twee soorten tests:
- een scan van alle `.py`-bestanden onder `src/shakka/domain/`, met minstens één bestand, zodat een padfout de test niet leeg laat slagen;
- een geparametriseerde scherptetest (AC-9).

De checker werkt met `ast`. Regels:
- **Imports (allowlist):** stdlib (`sys.stdlib_module_names`) minus de verboden modules, plus `pydantic`, `astral` en `shakka.domain` met submodules. Relatieve imports worden opgelost tegen het package van het bestand, zodat `from .. import db` als `shakka.db` herkend wordt.
- **Verboden modules:** de lijst uit het contract (`httpx`, `ddlpy`, `pywebpush`, `yaml`, `os`, `socket`, `subprocess`, `urllib`, `http`, `pathlib`) plus deze aanvulling: `io`, `shutil`, `tempfile`, `glob`, `sqlite3`, `ssl`, `asyncio`, `threading`, `multiprocessing`, `concurrent`, `signal`, `ctypes`, `importlib`, `sys`, `time`, `random`, `secrets`. De aanvulling bestaat uit stdlib-modules die I/O, procestoestand of niet-determinisme geven. Het contract laat die via "alleen de standaardbibliotheek" impliciet toe, maar ze botsen met "puur en deterministisch" (WP-05). Een latere WP die er één nodig heeft, onderbouwt dat in zijn blueprint en past de lijst aan.
- **Calls en attributen:**
  - `open(…)`, `__import__(…)`, `eval(…)` en `exec(…)`;
  - een call op een attribuut `now`, `today` of `utcnow`;
  - elk attribuut `utcnow`;
  - `time.time`.

AST in plaats van tekstzoeken, zoals WORK_PACKAGES voorschrijft. Comments en docstrings die `datetime.now()` noemen, worden daardoor niet gemeld. Dat is bewust: de regel gaat over code.

**Secret-hygiëne.** `ingest/tests/test_repo_hygiene.py` draait in pytest, dus ook in CI, zonder extra CI-commando. Het controleert:
1. `git grep --untracked -nE <regex uit AC-8> -- . ':!docs'` vanuit `REPO_ROOT` vindt niets. `--untracked` neemt ook nieuwe, nog niet gecommitte bestanden mee en respecteert `.gitignore`, dus `.env` valt erbuiten.
2. `.env.example` bevat exact de contractsleutels.
3. `.gitignore` bevat `supabase/.temp/` en `supabase/.branches/`, en `supabase/config.toml` bestaat.
4. `ci.yml` bevat de triggers en commando's.

De regex staat in de testfile zelf. Het JWT-fragment wordt daarom samengesteld (`"eyJhbGci" + "Oi"`), anders matcht de test zichzelf. Dummy-secrets in tests hebben na het prefix minder dan 20 tekens (bijv. `sb_secret_TESTVALUE`).

**Testisolatie.** `ingest/tests/conftest.py` heeft een autouse-fixture die alle Settings-variabelen uit `os.environ` haalt en `shakka.config.ENV_FILE` naar een niet-bestaand pad in `tmp_path` zet. Geen enkele test leest dus ooit Lars' echte `.env` of shell-omgeving.

**CI.** `.github/workflows/ci.yml`:
- één job `ingest` op `ubuntu-latest`, met `working-directory: ingest`;
- `permissions: contents: read`, concurrency per ref;
- `actions/checkout@v7` en `astral-sh/setup-uv` gepind op commit-SHA (v10.3.0);
- daarna exact `uv sync`, `uv run ruff check .`, `uv run ruff format --check .` en `uv run pytest`.

CI heeft geen secrets nodig. Dat moet zo blijven: bij `pull_request` vanuit een fork in een publieke repo zijn secrets niet beschikbaar. WP-01 voegt later job `db` toe en WP-13 job `web`.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `ingest/.python-version` | aanmaken | `3.12` |
| `ingest/pyproject.toml` | aanmaken | Projectmetadata, dependencies, script, dependency-group `dev`, build-system, ruff- en pytest-config (zie Interfaces). |
| `ingest/uv.lock` | aanmaken (gegenereerd door `uv lock`) | Lockfile, gecommit. |
| `ingest/src/shakka/__init__.py` | aanmaken | Alleen een module-docstring (`"""Shakka ingest, evaluation and alerting."""`). Geen imports. |
| `ingest/src/shakka/config.py` | aanmaken | `REPO_ROOT`, `ENV_FILE`, `DEFAULT_SPOTS_PATH`, `REQUIRED_ENV_VARS`, `Settings`, `get_settings()`. |
| `ingest/src/shakka/http.py` | aanmaken | `USER_AGENT`, `make_client()`. Enige plek in `src` met `httpx.Client(` (voorbereiding op WP-22 AC-1). |
| `ingest/src/shakka/doctor.py` | aanmaken | `DOCTOR_TIMEOUT_S`, `run_doctor()`. |
| `ingest/src/shakka/cli.py` | aanmaken | Click-groep `cli` met `--version` en `-h/--help`, command `doctor`, `main()`. |
| `ingest/src/shakka/domain/__init__.py` | aanmaken | Alleen een docstring die de puurheidsregel samenvat en verwijst naar `tests/test_domain_purity.py`. |
| `ingest/tests/conftest.py` | aanmaken | Autouse-fixture `_isolated_env`. |
| `ingest/tests/test_domain_purity.py` | aanmaken | Checker plus tests (AC-1, AC-9). |
| `ingest/tests/test_config.py` | aanmaken | Settings- en `get_settings`-tests. |
| `ingest/tests/test_http.py` | aanmaken | Tests voor `make_client`. |
| `ingest/tests/test_cli.py` | aanmaken | `--help`- en doctor-tests (AC-3, AC-4). |
| `ingest/tests/test_repo_hygiene.py` | aanmaken | Git-grep, `.env.example`, `.gitignore`, `supabase/config.toml`, `ci.yml` (AC-6 statisch, AC-7, AC-8). |
| `supabase/config.toml` | aanmaken via `supabase init` | Gegenereerd. Alleen `project_id` wordt handmatig `"shakka"`. Verder ongewijzigd: de expose- en RLS-instellingen zijn voor WP-01. |
| `supabase/.gitignore` | aanmaken als `supabase init` dit genereert | Ongewijzigd committen. |
| `.github/workflows/ci.yml` | aanmaken | Zie Interfaces. |
| `.env.example` | wijzigen | Zie Interfaces. `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` en `MAPTILER_KEY` verdwijnen. |
| `.gitignore` | wijzigen | Regels `supabase/.temp/` en `supabase/.branches/` toevoegen. Bestaande regels blijven. |
| `docs/RUNBOOK.md` | aanmaken | Zie Interfaces, sectie RUNBOOK. Nederlands. |

Geen andere bestanden. `docs/STATUS.md` wordt door de orchestrator bijgewerkt, niet door de builder.

## Interfaces en contracten

### `ingest/pyproject.toml`
```toml
[project]
name = "shakka"
version = "0.1.0"
description = "Shakka ingest, evaluation and alerting"
requires-python = ">=3.12,<3.13"
dependencies = [
    "click>=8.2,<9",
    "httpx>=0.28,<0.29",
    "pydantic>=2.11,<3",
    "pydantic-settings>=2.11,<3",
]

[project.scripts]
shakka = "shakka.cli:main"

[dependency-groups]
dev = [
    "pytest>=9.0,<10",
    "ruff>=0.17,<0.18",
]

[build-system]
requires = ["uv_build>=0.13.1,<0.14"]
build-backend = "uv_build"

[tool.ruff]
line-length = 100
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "DTZ"]

[tool.ruff.lint.isort]
known-first-party = ["shakka"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["-ra", "--strict-markers", "--strict-config"]
xfail_strict = true
```
- `DTZ` (flake8-datetimez) dwingt de afspraak "geen naive datetimes" ook statisch af.
- De bovengrens op ruff houdt de formattering stabiel tussen machines.
- `tests/` krijgt geen `__init__.py`. Met de standaard import-mode (`prepend`) kan WP-01 dan `from fakes import FakeSupabase` gebruiken.

### `shakka.config`
```python
REPO_ROOT: Final[Path]            # Path(__file__).resolve().parents[3]
ENV_FILE: Path                    # REPO_ROOT / ".env"; module global, read at call time
DEFAULT_SPOTS_PATH: Final[Path]   # REPO_ROOT / "data" / "spots.yaml"
REQUIRED_ENV_VARS: Final[tuple[str, ...]] = ("SUPABASE_URL", "SUPABASE_SECRET_KEY")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
        frozen=True,
    )
    supabase_url: str
    supabase_publishable_key: str | None = None
    supabase_secret_key: SecretStr
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None
    app_base_url: str | None = None
    vapid_public_key: str | None = None
    vapid_private_key: SecretStr | None = None
    vapid_subject: str | None = None
    spots_path: Path = DEFAULT_SPOTS_PATH

    @field_validator("supabase_url")
    @classmethod
    def _validate_supabase_url(cls, value: str) -> str: ...

def get_settings() -> Settings:
    """Load settings from the environment and, if it exists, REPO_ROOT/.env."""
    # env_file = ENV_FILE if ENV_FILE.is_file() else None
    # return Settings(_env_file=env_file)
```
Regels van `_validate_supabase_url`. Parse met `urllib.parse.urlsplit` (config valt niet onder het domein, dus dit mag).
- Scheme `https`: host moet niet-leeg zijn.
- Scheme `http`: alleen toegestaan als host ∈ {`localhost`, `127.0.0.1`, `::1`}.
- `path` moet `""` of `"/"` zijn, en `query` en `fragment` moeten leeg zijn.
- Teruggegeven wordt `f"{scheme}://{netloc}"`, dus zonder trailing slash.
- Bij een fout volgt `ValueError("expected https://<project-ref>.supabase.co (http only for localhost), without path")`. De invoer staat niet in de melding.

### `shakka.http`
```python
USER_AGENT: Final[str]  # f"shakka-ingest/{version} (+https://github.com/LarsTout/shakka)"
                        # version = importlib.metadata.version("shakka"), fallback "0+unknown"

def make_client(*, timeout: float = 30.0) -> httpx.Client:
    """Return an httpx.Client with an explicit timeout and the Shakka User-Agent."""
    # ValueError if not (math.isfinite(timeout) and timeout > 0)
    # httpx.Client(timeout=httpx.Timeout(timeout), headers={"User-Agent": USER_AGENT},
    #              follow_redirects=False)
```

### `shakka.doctor`
```python
DOCTOR_TIMEOUT_S: Final[float] = 10.0

def run_doctor(*, echo: Callable[[str], None]) -> int:
    """Check configuration and Supabase REST connectivity. Returns the exit code (0 or 1).
    Never outputs variable values, the Supabase URL, response bodies or exception messages."""
```
`run_doctor` haalt `get_settings` en `make_client` op als namen uit de module `shakka.doctor` (`from shakka.config import get_settings` en `from shakka.http import make_client` bovenin), zodat tests `shakka.doctor.make_client` kunnen monkeypatchen.

Exacte uitvoerregels (statuswoord links uitgelijnd op 8 tekens, Engels):

| Situatie | Regel |
|---|---|
| verplicht veld ontbreekt | `missing SUPABASE_URL` / `missing SUPABASE_SECRET_KEY` |
| validatiefout `supabase_url` | `invalid SUPABASE_URL: expected https://<project-ref>.supabase.co (http only for localhost), without path` |
| andere validatiefout op veld X | `invalid <X.upper()>` |
| verplicht veld in orde | `ok      SUPABASE_URL` / `ok      SUPABASE_SECRET_KEY` (alleen voor velden zonder fout) |
| publishable gezet | `ok      SUPABASE_PUBLISHABLE_KEY` (alleen als settings geladen zijn) |
| publishable leeg | `unset   SUPABASE_PUBLISHABLE_KEY (optional)` |
| secret zonder prefix `sb_secret_` | `warn    SUPABASE_SECRET_KEY does not start with sb_secret_ (legacy keys stop working end of 2026)` |
| publishable zonder prefix `sb_publishable_` | `warn    SUPABASE_PUBLISHABLE_KEY does not start with sb_publishable_` |
| config incompleet | `skip    Supabase REST check (configuration incomplete)` en geen request |
| 2xx | `ok      Supabase REST API reachable (HTTP <code>)` |
| 401 of 403 | `error   Supabase REST API rejected the key (HTTP <code>); SUPABASE_SECRET_KEY must be a secret key (sb_secret_...)` |
| 404 | `error   Supabase REST API returned HTTP 404; check SUPABASE_URL` |
| 3xx | `error   Supabase REST API redirected (HTTP <code>); check SUPABASE_URL` |
| andere status | `error   Supabase REST API returned HTTP <code>` |
| `httpx.TimeoutException` | `error   Supabase REST API timed out after 10s` |
| andere `httpx.HTTPError` | `error   Supabase REST API unreachable (<type(exc).__name__>)` |
| einde | `doctor: ok` (exit 0) of `doctor: failed` (exit 1) |

Volgorde: env-regels in de volgorde URL, secret, publishable; dan waarschuwingen; dan de REST-regel; dan de eindregel. De request: `client.get(f"{settings.supabase_url}/rest/v1/", headers={"apikey": settings.supabase_secret_key.get_secret_value()})` binnen `with make_client(timeout=DOCTOR_TIMEOUT_S) as client:`. Geen `Authorization`-header en geen query-parameters.

### `shakka.cli`
```python
@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="shakka", prog_name="shakka")
def cli() -> None:
    """Shakka ingest and admin tooling."""

@cli.command()
def doctor() -> None:
    """Check configuration and Supabase connectivity."""
    # from shakka.doctor import run_doctor  (lazy)
    # raise SystemExit(run_doctor(echo=click.echo))

def main() -> None:
    cli()
```
Latere groepen (`spots`, `forecast`, `tides`, `contracts`, `alerts`, `evaluate`, `admin`, `run-hourly`, `marine`) komen als `@cli.group()` of `@cli.command()` in dit bestand, met lazy imports in de commandfunctie.

### `.env.example` (exacte inhoud)
```
# Kopieer naar .env in de repo-root en vul in. .env staat in .gitignore.
# Uitleg per variabele: docs/RUNBOOK.md. Zet hier nooit echte waarden.
SUPABASE_URL=
SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SECRET_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
APP_BASE_URL=
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:
```

### `.gitignore` (toevoegen aan het eind)
```
supabase/.temp/
supabase/.branches/
```

### `.github/workflows/ci.yml` (exacte inhoud)
```yaml
name: ci

on:
  push:
  pull_request:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  ingest:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    defaults:
      run:
        working-directory: ingest
    env:
      UV_LOCKED: "1"
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@1c37ad07a6a961277cf70c0d37d6f313000f5884 # v10.3.0
        with:
          working-directory: ingest
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pytest
```
uv leest Python 3.12 uit `ingest/.python-version`. De cache staat standaard aan op GitHub-hosted runners (`enable-cache: auto`).

### `docs/RUNBOOK.md` (secties, Nederlands)
1. **Vereisten:** uv (`brew install uv` of het installatiescript van astral.sh), Supabase CLI (`brew install supabase/tap/supabase`), Docker Desktop of OrbStack (alleen voor `supabase start`, vanaf WP-01).
2. **Ingest lokaal:** `cd ingest && uv sync`, de testcommando's, de lintcommando's en `uv run shakka doctor`. Commando's draaien vanuit `ingest/`; vanuit de root kan `uv run --project ingest shakka doctor`.
3. **`.env` invullen:** `cp .env.example .env` in de repo-root. Waar je `SUPABASE_URL` en de nieuwe sleutels vindt (Dashboard → Project Settings → API Keys; de URL is `https://<project-ref>.supabase.co`). Waarschuwing dat `SUPABASE_ANON_KEY` en `SUPABASE_SERVICE_ROLE_KEY` niet meer gelezen worden. Wat elke `doctor`-regel betekent (401 = verkeerde sleutel, 404 = verkeerde URL).
4. **Secrets, alleen namen:** tabel met variabele, plek (`.env`, GitHub Secret, Actions-variable) en vanaf welke WP. Overgenomen uit het env-contract in WORK_PACKAGES.md, alleen de ingest-variabelen. Vermelding dat de Supabase access token en het DB-wachtwoord bij Lars blijven en nergens in de repo komen.
5. **Supabase CLI koppelen:** `supabase login` (browser, token blijft lokaal) en `supabase link --project-ref <ref>` (vraagt het DB-wachtwoord; niet opslaan in de repo). `supabase/.temp/` bevat lokale koppelinfo en is gitignored.
6. **Lokale stack (vanaf WP-01):** `supabase start` en `supabase stop`. `supabase status` toont de lokale URL (`http://127.0.0.1:54321`) en de lokale publishable en secret key. Hoe je `.env` tijdelijk naar de lokale stack laat wijzen.
7. **CI:** wat de job `ingest` draait, en hoe je de laatste run bekijkt (`gh run list --workflow ci.yml --limit 1`). CI gebruikt geen secrets.

## Edge cases
| # | Geval | Gedrag |
|---|---|---|
| E1 | `.env` gekopieerd uit `.env.example`, waarden leeg | `env_ignore_empty` → `missing`, exit 1. |
| E2 | Geen `.env` | `get_settings` gebruikt alleen de OS-omgeving, zonder fout. |
| E3 | Variabele zowel in OS-env als in `.env` | OS-env wint. |
| E4 | Onbekende of legacy sleutels in `.env` (`SUPABASE_ANON_KEY`, `PUBLIC_*`, `MAPTILER_KEY`) | Genegeerd (`extra="ignore"`), geen crash. |
| E5 | `SUPABASE_URL` met trailing slash | Genormaliseerd. Request gaat naar exact `…supabase.co/rest/v1/`. |
| E6 | `SUPABASE_URL` met pad (`…/rest/v1`), query, `ftp://` of `http://` naar een remote host | `invalid SUPABASE_URL`, geen request, exit 1. |
| E7 | `http://127.0.0.1:54321` (lokale stack) | Geldig. |
| E8 | Publishable key in het secret-veld | Waarschuwing over het prefix. De server geeft 401 → hint, exit 1. |
| E9 | Legacy JWT als secret | Waarschuwing. Exit volgt de HTTP-status. |
| E10 | Netwerkfout, DNS-fout of timeout | `error`-regel met alleen de klassenaam, geen traceback, exit 1. |
| E11 | 3xx (bijv. een verkeerde host die doorstuurt) | Niet gevolgd, `error … redirected`, exit 1. De key gaat niet naar een andere host. |
| E12 | Response body bevat tekst | Wordt nooit getoond. |
| E13 | Uitvoer bij gedeeltelijke config | Bevat geen waarden, ook niet die van gezette variabelen (URL, Telegram-token). |
| E14 | Hygiëne-regex matcht de eigen testfile | Voorkomen door het samengestelde JWT-fragment. Dummy-secrets hebben minder dan 20 tekens na het prefix. |
| E15 | `REPO_ROOT` fout (niet-editable install) | Test `test_repo_root_points_to_repo` faalt. |
| E16 | Domeinmap leeg of verkeerd pad | Scantest faalt bij 0 gevonden bestanden. |
| E17 | Relatieve import in het domein naar I/O (`from ..db import X`, `from .. import jobs`) | Opgelost naar `shakka.db` / `shakka.jobs` → overtreding. |
| E18 | Syntaxfout in een domeinbestand | Gemeld als overtreding `syntax_error` in plaats van een crash van de checker. |
| E19 | `import shakka` of `from shakka import http` in het domein | Overtreding: alleen `shakka.domain` en submodules zijn toegestaan. |
| E20 | Tests op Lars' machine met geëxporteerde `SUPABASE_*`-shellvariabelen | De autouse-fixture verwijdert ze. Tests lezen nooit de echte `.env`. |
| E21 | Fork-PR in de publieke repo | CI heeft geen secrets nodig en slaagt gewoon. |
| E22 | `make_client(timeout=0)`, negatief, `inf` of `nan` | `ValueError`. |

## Testplan
Alle tests draaien met `cd ingest && uv run pytest`. Geen echte netwerk-calls in tests: doctor-tests gebruiken `httpx.MockTransport` via een gemonkeypatchte `shakka.doctor.make_client`, die `httpx.Client(transport=…)` teruggeeft. Dit staat in `tests/`, dus de grep van WP-22 AC-1 op `src` blijft schoon. Een gedeelde helper in `test_cli.py` maakt een recorder-transport dat de requests in een lijst bewaart.

**AC-1** (`uv sync && uv run pytest` groen, met `test_domain_purity.py`)
- `test_domain_purity.py::test_domain_package_is_pure`: scant `Path(shakka.domain.__file__).parent.rglob("*.py")`, eist minstens 1 bestand en 0 overtredingen. Overtredingen staan in de assert-melding.
- De verifier draait de volledige suite.

**AC-2** (ruff): geen test. De verifier draait de commando's. De builder draait ze na elke stap.

**AC-3** (`shakka --help`)
- `test_cli.py::test_help_lists_doctor`: `CliRunner().invoke(cli, ["--help"])` → `exit_code == 0` en `"doctor"` in de uitvoer.
- `test_cli.py::test_version_option`: `--version` → exit 0, uitvoer bevat `shakka`.
- De verifier draait ook echt `uv run shakka --help`.

**AC-4** (doctor met lege omgeving)
- `test_doctor_empty_env_reports_missing`: lege env (fixture) → exit 1. Uitvoer bevat `missing SUPABASE_URL`, `missing SUPABASE_SECRET_KEY`, `skip` en `doctor: failed`. De recorder telt 0 requests.
- `test_doctor_partial_env_does_not_leak_values`: `SUPABASE_URL=https://leakcheckref.supabase.co`, `TELEGRAM_BOT_TOKEN=123:TESTTOKEN` en `SUPABASE_PUBLISHABLE_KEY=sb_publishable_TESTPUB` → exit 1, `missing SUPABASE_SECRET_KEY` staat in de uitvoer, en `leakcheckref`, `TESTTOKEN` en `TESTPUB` niet.
- `test_doctor_empty_string_counts_as_missing`: `SUPABASE_SECRET_KEY=""` → `missing SUPABASE_SECRET_KEY`.
- `test_doctor_reads_env_file`: tmp-`.env` met beide verplichte waarden, `ENV_FILE` gemonkeypatcht, 200-mock → exit 0.

**AC-5** (`uv run shakka doctor` met Lars' `.env`): handmatig door de verifier, anders `NEEDS_LARS`. Aanvullend, met mocks:
- `test_doctor_success`: geldige env + 200 → exit 0, `doctor: ok`. Precies 1 request:
  - methode `GET`, URL exact `https://testref.supabase.co/rest/v1/`;
  - header `apikey == "sb_secret_TESTVALUE"`, geen `authorization`-header;
  - de key staat niet in `str(request.url)`;
  - `user-agent` begint met `shakka-ingest/`.
- `test_doctor_trailing_slash_url`: `SUPABASE_URL=https://testref.supabase.co/` → zelfde request-URL.
- `test_doctor_http_status` (geparametriseerd: 401, 403, 404, 500, 302) → exit 1, juiste regel uit de tabel, en `sb_secret_TESTVALUE` niet in de uitvoer.
- `test_doctor_network_error`: transport gooit `httpx.ConnectError("boom testref")` → exit 1, `unreachable (ConnectError)`, `testref` en `boom` niet in de uitvoer.
- `test_doctor_timeout`: transport gooit `httpx.ReadTimeout("x")` → `timed out after 10s`, exit 1.
- `test_doctor_invalid_url` (geparametriseerd: `ftp://x.supabase.co`, `http://testref.supabase.co`, `https://testref.supabase.co/rest/v1`, `https://testref.supabase.co?x=1`) → `invalid SUPABASE_URL`, 0 requests, exit 1.
- `test_doctor_local_http_url_allowed`: `http://127.0.0.1:54321` + 200 → exit 0, request naar `http://127.0.0.1:54321/rest/v1/`.
- `test_doctor_prefix_warnings`: secret `legacy-test-key` + 200 → `warn    SUPABASE_SECRET_KEY`, exit 0. Publishable `wrong-prefix` → `warn    SUPABASE_PUBLISHABLE_KEY`.
- `test_doctor_publishable_unset_is_optional`: zonder publishable + 200 → `unset   SUPABASE_PUBLISHABLE_KEY (optional)`, exit 0.

`test_config.py`:
- `test_repo_root_points_to_repo`: `(REPO_ROOT / "ingest" / "pyproject.toml").is_file()`.
- `test_defaults`: optionele velden zijn `None` en `spots_path == REPO_ROOT / "data" / "spots.yaml"`.
- `test_env_overrides_env_file`: tmp-`.env` met URL A en OS-env met URL B → B.
- `test_unknown_keys_in_env_file_ignored`: tmp-`.env` met `SUPABASE_ANON_KEY=x` en `PUBLIC_FOO=y` plus de verplichte velden → geen fout.
- `test_missing_env_file_is_fine`: `ENV_FILE` naar een niet-bestaand pad, verplichte velden via env → laadt.
- `test_secrets_not_in_repr`: `sb_secret_TESTVALUE` en `123:TESTTOKEN` staan niet in `repr(settings)` of `str(settings)`.
- `test_supabase_url_validation` (geparametriseerd, geldig en ongeldig, zoals hierboven).

`test_http.py`:
- `test_default_timeout`: `make_client().timeout` heeft connect, read, write en pool gelijk aan 30.0.
- `test_custom_timeout`: 5.0.
- `test_invalid_timeout` (0, -1, `float("inf")`, `float("nan")`) → `ValueError`.
- `test_user_agent`: header is `USER_AGENT`, begint met `shakka-ingest/`, bevat geen `Mozilla` en geen `@`.
- `test_no_redirect_follow`: `client.follow_redirects is False`.

**AC-6** (CI)
- `test_repo_hygiene.py::test_ci_workflow_contract` (tekstcontrole, geen yaml-dependency): `.github/workflows/ci.yml` bevat de regels `push:`, `pull_request:`, `ingest:`, `working-directory: ingest`, `run: uv sync`, `run: uv run ruff check .`, `run: uv run ruff format --check .` en `run: uv run pytest`.
- De groene run zelf: `gh run list --workflow ci.yml --limit 1` door de verifier, of `NEEDS_LARS`.

**AC-7**
- `test_supabase_config_exists`: `(REPO_ROOT / "supabase" / "config.toml").is_file()`.
- `test_gitignore_has_supabase_entries`: de regels van `.gitignore` bevatten `supabase/.temp/` en `supabase/.branches/`.

**AC-8**
- `test_env_example_exact`: niet-lege regels die niet met `#` beginnen, gesplitst op de eerste `=`. De sleutels zijn exact (als lijst, in contractvolgorde) de 9 uit het contract, alle waarden zijn `""` behalve `VAPID_SUBJECT == "mailto:"`.
- `test_no_keys_in_repo`: `subprocess.run(["git", "grep", "--untracked", "-nE", PATTERN, "--", ".", ":!docs"], cwd=REPO_ROOT)`. Returncode 1 = pass, 0 = fail met de treffers in de melding, anders fail met stderr. `PATTERN = r"sb_(secret|publishable)_[A-Za-z0-9_-]{20,}|" + "eyJhbGci" + "Oi"`.
- De verifier draait daarnaast het letterlijke commando uit AC-8.

**AC-9** (scherpte van de puurheidstest)
- `test_checker_flags` (geparametriseerd, elk minstens 1 overtreding, module `shakka.domain.probe`):
  - `import httpx`
  - `from os import environ`
  - `from datetime import datetime\nx = datetime.now()\n`
  - `open("x")`
  - `import os.path`
  - `import yaml`
  - `import pathlib`
  - `from urllib.parse import urlsplit`
  - `import http.client`
  - `import requests`
  - `import shakka`
  - `from shakka import http`
  - `from shakka.db import SupabaseRest`
  - `from .. import db`
  - `from ..jobs import evaluate`
  - `from datetime import date\nd = date.today()\n`
  - `from datetime import datetime\nx = datetime.utcnow()\n`
  - `import time\nt = time.time()\n`
  - `__import__("os")`
  - `def f(:` (syntax_error)
- `test_checker_allows` (geparametriseerd, 0 overtredingen):
  - `from pydantic import BaseModel` (het verplichte negatieve geval)
  - `from pydantic import BaseModel, ConfigDict`
  - `from datetime import UTC, datetime, time, timedelta`
  - `from zoneinfo import ZoneInfo`
  - `import math`
  - `from astral.sun import sun`
  - `from shakka.domain.spot import Level`
  - `from . import spot`
  - `from .spot import Level`
  - `def f(now):\n    return now\n`

Checker-API in de testfile:
```python
@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    rule: str      # "forbidden_import" | "forbidden_call" | "syntax_error"
    detail: str
    def __str__(self) -> str: return f"{self.path}:{self.line}: {self.rule}: {self.detail}"

def check_source(source: str, *, module: str = "shakka.domain.probe",
                 is_package: bool = False, path: str = "<string>") -> list[Violation]: ...
def module_name_for(file: Path, src_root: Path) -> tuple[str, bool]: ...  # ("shakka.domain.x", is_package)
```
Regels voor importresolutie:
- Een import is toegestaan als de top-level naam in `sys.stdlib_module_names` staat en niet in `FORBIDDEN_MODULES`, of in `{"pydantic", "astral"}` staat, of als de volledige naam `shakka.domain` is of begint met `shakka.domain.`.
- Bij `from X import a, b` met X = `shakka` (of relatief opgelost naar `shakka`) wordt elke `X.a` apart getoetst.
- Een relatieve import met level n wordt opgelost vanaf het package. Voorbij `shakka` is het een overtreding.

## Externe afhankelijkheden

| Package | Versie-eis | Reden | Gecontroleerd |
|---|---|---|---|
| `click` | `>=8.2,<9` (laatste: 8.5.0) | CLI met geneste groepen, `CliRunner` voor tests | https://pypi.org/pypi/click/json |
| `httpx` | `>=0.28,<0.29` (laatste: 0.28.1) | HTTP-client uit de stack, `MockTransport` voor tests | https://pypi.org/pypi/httpx/json |
| `pydantic` | `>=2.11,<3` (laatste: 2.14.x) | Stack. `SecretStr` en validatie | https://pypi.org/pypi/pydantic/json |
| `pydantic-settings` | `>=2.11,<3` (laatste: 2.16.0, uitgebracht op 14-10-2026) | Env plus `.env` lezen. Trekt `python-dotenv` mee | https://pypi.org/pypi/pydantic-settings/json, https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/ (`env_ignore_empty`, `extra` standaard `forbid`, `_env_file`, env gaat vóór dotenv) |
| `pytest` (dev) | `>=9.0,<10` (laatste: 9.1.1) | Tests | https://pypi.org/pypi/pytest/json |
| `ruff` (dev) | `>=0.17,<0.18` (laatste: 0.17.0) | Lint en format | https://pypi.org/pypi/ruff/json |
| `uv_build` (build) | `>=0.13.1,<0.14` | Build-backend van uv. Src-layout `src/<package>/__init__.py` is de standaard | https://docs.astral.sh/uv/concepts/build-backend/ |

Overig:
- **uv-omgevingsvariabele `UV_LOCKED`** (sinds uv 0.4.25): gelijk aan `--locked`. https://docs.astral.sh/uv/reference/environment/
- **`astral-sh/setup-uv`** v10.3.0, gepind op SHA `1c37ad07a6a961277cf70c0d37d6f313000f5884`. Dit is de pin uit de README. Er wordt geen zwevende major-tag gedocumenteerd. Input `working-directory` bepaalt waar het de config zoekt. https://github.com/astral-sh/setup-uv, https://github.com/astral-sh/setup-uv/releases
- **`actions/checkout@v7`** (laatste: v7.0.1; de README gebruikt `@v7`). https://github.com/actions/checkout
- **Supabase CLI** (npm `supabase` 2.121.0): `supabase init` maakt `supabase/config.toml` en is standaard niet-interactief; `-i` maakt het interactief, `--force` overschrijft. https://supabase.com/docs/reference/cli/supabase-init, https://registry.npmjs.org/supabase/latest
- **Supabase REST, API-sleutels:**
  - nieuwe sleutels gaan via de `apikey`-header, niet als `Authorization: Bearer`;
  - een secret key geeft 401 bij een browser-achtige `User-Agent`;
  - legacy-sleutels vervallen eind 2026;
  - `supabase start` toont lokaal een publishable en een secret key.

  https://supabase.com/docs/guides/api/api-keys
- **Endpoint:** `GET {SUPABASE_URL}/rest/v1/`, header `apikey: sb_secret_…`, geen parameters. Het gedrag met de publishable key (401 "Secret API key required") staat niet in de publieke documentatie. De bron is de controle van 14 oktober 2026 die in WORK_PACKAGES.md staat.

Geen betaalde diensten. CI gebruikt gratis GitHub Actions-minuten (publieke repo).

## Risico's
- **R1. Root-endpoint verandert.** Supabase kan het gedrag van `GET /rest/v1/` wijzigen; het staat niet in de publieke documentatie. Dan faalt `doctor` terwijl de koppeling werkt. Mitigatie: vaste, duidelijke foutregels per statuscode. Als dit gebeurt, kan WP-01 doctor laten overstappen op een tabel-select (bijv. `spots?select=id&limit=1`) zodra die tabel bestaat.
- **R2. pydantic-settings 2.16.0 is vandaag uitgebracht.** De lockfile pakt waarschijnlijk die versie. Bij een regressie zet de builder de bovengrens op `<2.16` en noteert dat in `deviations.md` (raakt het ontwerp niet).
- **R3. SHA-pin van setup-uv veroudert.** Geen veiligheidsprobleem, alleen onderhoud. Dependabot valt buiten scope.
- **R4. De aanvulling op de verboden stdlib-modules kan een latere WP hinderen.** Bijvoorbeeld als die `random` nodig heeft. Mitigatie: zo'n wijziging hoort expliciet in de blueprint van die WP, en de lijst staat op één plek.
- **R5. Lars' `.env` gebruikt nog de oude namen.** Dan faalt AC-5. Mitigatie: `doctor` noemt de nieuwe naam als `missing`, en RUNBOOK sectie 3 waarschuwt hiervoor.
- **R6. Supabase CLI ontbreekt bij de builder.** Fallback: `npx --yes supabase@2.121.0 init`. Lukt dat ook niet, dan stopt de builder en noteert het in `deviations.md`.

## Buiten scope
- Databaseschema, migraties, pgTAP, CI-job `db` en de expose/RLS-instellingen in `config.toml` (WP-01).
- `shakka.db` / `SupabaseRest` en `FakeSupabase` (WP-01).
- `/web`, `web/.env.example` en CI-job `web` (WP-13).
- De cron-workflow `hourly.yml` (WP-11).
- Retry/backoff-helper (WP-03, WP-22).
- `doctor`-controles voor Telegram, VAPID of `APP_BASE_URL` (latere WP's breiden `run_doctor` uit als hun blueprint dat vraagt).
- Dependabot, pre-commit hooks, type checker (mypy/pyright).
- Branch protection en GitHub-instellingen (Lars).
- `docs/STATUS.md` bijwerken (orchestrator).

## Stappenplan voor de builder
Werk op branch `wp/WP-00`. Lees of print `.env` nooit. Draai na elke stap `cd ingest && uv run pytest && uv run ruff check . && uv run ruff format --check .` (vanaf stap 2). Eén commit per stap, commitberichten in het Engels.

1. **Skelet.** Maak `ingest/.python-version`, `ingest/pyproject.toml` (exact zoals in Interfaces), `ingest/src/shakka/__init__.py`, `ingest/src/shakka/domain/__init__.py` en een minimale `ingest/src/shakka/cli.py` met alleen de groep `cli`, `--version` en `main()`. Draai `cd ingest && uv lock && uv sync`, en controleer dat `uv run shakka --help` exit 0 geeft. Commit `chore(ingest): scaffold uv project`.
2. **Puurheidstest (eerst de test).** Schrijf `ingest/tests/test_domain_purity.py` met de checker, de repo-scan en de geparametriseerde gevallen uit het Testplan (AC-9). Draai pytest: alles groen (het domein bevat alleen een docstring). Controleer kort de scherpte: zet tijdelijk `import os` in `domain/__init__.py`, zie de scan falen, en draai het terug. Commit `test(ingest): enforce domain purity with AST checks`.
3. **Config (eerst de tests).** Schrijf `ingest/tests/conftest.py` (autouse `_isolated_env`: `monkeypatch.delenv(name, raising=False)` voor elke `field.upper()` uit `Settings.model_fields`, en `monkeypatch.setattr(shakka.config, "ENV_FILE", tmp_path / "absent.env")`) en `ingest/tests/test_config.py`. Implementeer daarna `shakka/config.py` tot alles groen is. Commit `feat(ingest): add settings loaded from env and .env`.
4. **HTTP (eerst de tests).** `ingest/tests/test_http.py`, daarna `shakka/http.py`. Commit `feat(ingest): add http client factory with timeout and user agent`.
5. **Doctor (eerst de tests).** Schrijf `ingest/tests/test_cli.py` (help, version, alle doctor-tests). Implementeer `shakka/doctor.py` volgens de uitvoertabel en voeg het command `doctor` toe aan `shakka/cli.py`. Controleer dat `uv run shakka --help` `doctor` toont. Commit `feat(ingest): add shakka doctor command`.
6. **Repo-hygiëne.** Pas `.env.example` aan (exacte inhoud) en voeg de twee regels toe aan `.gitignore`. Draai in de repo-root `supabase init`, of als fallback `npx --yes supabase@2.121.0 init`, zonder `-i`. Zet `project_id = "shakka"` in `supabase/config.toml`; verder niets aanpassen. Schrijf `ingest/tests/test_repo_hygiene.py`, behalve `test_ci_workflow_contract`. Draai ook het letterlijke `git grep`-commando uit AC-8 vanuit de root: geen treffers. Commit `chore: init supabase project and env contract`.
7. **CI.** Maak `.github/workflows/ci.yml` (exacte inhoud) en voeg `test_ci_workflow_contract` toe. Commit `ci: add ingest lint and test workflow`.
8. **RUNBOOK.** Schrijf `docs/RUNBOOK.md` met de zeven secties, in het Nederlands, met alleen namen van secrets. Commit `docs: add runbook for local setup and secrets`.
9. **Eindcontrole.**
   - Draai `cd ingest && uv sync && uv run pytest` en `uv run ruff check . && uv run ruff format --check .`.
   - Draai `uv run shakka --help`.
   - Bestaat `/Users/larst/Dev/Shakka/.env`, draai dan `uv run shakka doctor` en noteer alleen de exitcode en de statuswoorden. Anders is AC-5 `NEEDS_LARS`.
   - Push `wp/WP-00` alleen met uitdrukkelijke toestemming (A5). Daarna `gh run list --workflow ci.yml --limit 1`.
