# Verificatie WP-00, ronde 2
Resultaat: PASS

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `cd ingest && uv sync && uv run pytest`: 85 passed, waaronder `tests/test_domain_purity.py` (31 tests). Een tijdelijke `import os` in `domain/__init__.py` laat `test_domain_package_is_pure` falen (1 failed, 30 passed); teruggezet via `git checkout`, werkboom schoon. |
| AC-2 | PASS | `uv run ruff check .`: "All checks passed!". `uv run ruff format --check .`: "12 files already formatted". |
| AC-3 | PASS | `uv run shakka --help` exit 0, toont `doctor`. `--version` gedekt in `test_cli.py`. |
| AC-4 | PASS | `test_cli.py` doctor-tests (lege env, partial env zonder lek van `leakcheckref`/`TESTTOKEN`/`TESTPUB`, lege string, env-file) groen binnen de 85. |
| AC-5 | PASS | `.env` aanwezig (inhoud niet gelezen). `uv run shakka doctor`: `ok` voor URL, secret en publishable, `ok Supabase REST API reachable (HTTP 200)`, `doctor: ok`, exit 0. Geen waarden in de uitvoer. Mock-tests uit het testplan groen. |
| AC-6 | PASS | `ci.yml` komt overeen met de blueprint (triggers `push`/`pull_request`, exact de commando's van AC-1 en AC-2); `test_ci_workflow_contract` groen. `wp/WP-00` staat nu op origin (HEAD == `origin/wp/WP-00` == `fffa55a`). `gh run list --branch wp/WP-00`: run 38614820663 op `fffa55a`, conclusion `success`, job `ingest` success. Let op: `gh run list --workflow ci.yml` zonder `--branch` geeft pas resultaat zodra `ci.yml` op de default branch `develop` staat. |
| AC-7 | PASS | `supabase/config.toml` bestaat (`project_id = "shakka"`); `.gitignore` bevat `supabase/.temp/` en `supabase/.branches/`; tests in `test_repo_hygiene.py` groen. |
| AC-8 | PASS | `.env.example` heeft exact de 9 sleutels, alleen `VAPID_SUBJECT=mailto:` heeft een waarde. `git grep --untracked -nE "sb_(secret|publishable)_[A-Za-z0-9_-]{20,}|eyJhbGciOi" -- . ':!docs'` geeft returncode 1 (geen treffers). |
| AC-9 | PASS | `test_checker_flags` en `test_checker_allows` (geparametriseerd; o.a. `import httpx`, `from os import environ`, `datetime.now()`, `open("x")` gemeld; `from pydantic import BaseModel` niet) groen. |

## Harde regels
- Geen secrets in de diff: grep schoon; `.env` niet getrackt (`git ls-files`). Tests gebruiken dummy-waarden.
- Geen client-side Open-Meteo, geen scraping: `grep -i "open-meteo|scrap"` in `ingest/src` en `.github` zonder treffers. Geen `/web` in de diff.
- Geen nieuwe betaalde dienst: alleen gratis GitHub Actions en Supabase free.
- Bronvermelding en offshore `no_go`: niet geraakt in deze WP.
- `httpx.Client(` staat alleen in `shakka/http.py`. Doctor print geen waarden, URL, body of exceptionmelding.

## Scope en blueprint
- De gewijzigde bestanden komen overeen met de bestandentabel van de blueprint; `docs/STATUS.md` is de orchestrator-wijziging. Geen bestanden buiten scope.
- Geen `deviations.md`. Kleine verschillen die niet in strijd zijn met de blueprint en uit review N-5 komen: `_validate_supabase_url` toetst op `urlsplit().hostname` en weigert `?`/`#` in de ruwe waarde. Userinfo wordt niet geweigerd.
- Niet-blokkerend, niet verwerkt uit de review: N-3 (`Field(default_factory=datetime.now)` zonder call wordt door de checker niet gemeld), N-4 (`httpx.InvalidURL` of niet-ASCII key in de header geeft een traceback in doctor). Beide kunnen in een latere WP worden opgepakt.

## Problemen
Geen.
