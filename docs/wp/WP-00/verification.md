# Verificatie WP-00, ronde 1
Resultaat: NEEDS_LARS

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `cd ingest && uv sync && uv run pytest`: 85 passed, waaronder `tests/test_domain_purity.py` (31 tests). Tijdelijk `import os` in `domain/__init__.py` laat `test_domain_package_is_pure` falen (daarna teruggezet). |
| AC-2 | PASS | `uv run ruff check .` geeft "All checks passed!"; `uv run ruff format --check .` geeft "12 files already formatted". |
| AC-3 | PASS | `uv run shakka --help` exit 0, toont `doctor`. `--version` is gedekt in `test_cli.py`. |
| AC-4 | PASS | `test_cli.py` doctor-tests (lege env, partial env zonder lek, lege string, env-file) groen. Controleren: exit 1, `missing`-regels, geen waarden. |
| AC-5 | PASS | `.env` aanwezig (inhoud niet gelezen). `uv run shakka doctor` toont `ok` voor URL, secret en publishable, `ok Supabase REST API reachable (HTTP 200)`, `doctor: ok`, exit 0. Aanvullend de mock-tests uit het testplan groen. |
| AC-6 | NEEDS_LARS | Statisch gedekt: `ci.yml` is identiek aan de blueprint en `test_ci_workflow_contract` is groen. `wp/WP-00` staat niet op origin (`git branch -r` toont alleen develop en main). `gh run list --workflow ci.yml` geeft HTTP 404 (workflow staat niet op de default branch). Nodig: Lars pusht de branch of opent de PR en bevestigt een groene run (`gh pr checks`). |
| AC-7 | PASS | `supabase/config.toml` bestaat met `project_id = "shakka"`; `.gitignore` bevat `supabase/.temp/` en `supabase/.branches/`; tests in `test_repo_hygiene.py` groen. |
| AC-8 | PASS | `.env.example` is identiek aan de blueprint (9 sleutels, alleen `VAPID_SUBJECT=mailto:`). `git grep --untracked -nE "sb_(secret|publishable)_[A-Za-z0-9_-]{20,}\|eyJhbGciOi" -- . ':!docs'` geeft returncode 1 (geen treffers). |
| AC-9 | PASS | `test_checker_flags` en `test_checker_allows` (geparametriseerd, o.a. `import httpx`, `from os import environ`, `datetime.now()`, `open("x")`, en `from pydantic import BaseModel` toegestaan) groen. |

## Harde regels
- Geen secrets in de diff: grep schoon; `.env` is niet getrackt (`git ls-files` toont hem niet). Tests gebruiken dummy-waarden.
- Geen client-side Open-Meteo, geen scraping: `grep -i "open-meteo|scrap"` in `ingest/src` en `.github` zonder treffers. Geen `/web` in de diff.
- Geen nieuwe betaalde dienst: alleen gratis GitHub Actions en Supabase free.
- Bronvermelding en offshore-regel: niet van toepassing in deze WP, niet geraakt.
- `httpx.Client(` staat alleen in `shakka/http.py`. Doctor print geen waarden, URL, body of exceptionmelding.

## Scope en blueprint
- De 21 gewijzigde bestanden komen exact overeen met de bestandentabel van de blueprint; `docs/STATUS.md` is de orchestrator-wijziging (uncommitted). Geen bestanden buiten scope.
- Geen `deviations.md`. Waargenomen verschillen zijn klein en niet in strijd met de blueprint: `_validate_supabase_url` toetst op `urlsplit().hostname` (review N-5). Het weigeren van userinfo (`https://user:pass@host`) is niet geimplementeerd; die review-opmerking was niet-blokkerend.
- Review-opmerking N-4 (brede `except Exception` in doctor) is niet verwerkt: `httpx.InvalidURL` of een niet-ASCII key geeft een traceback. Niet-blokkerend.

## Problemen
Geen faalpunten. Open: F-1 (NEEDS_LARS): AC-6 vereist een groene CI-run op een gepushte branch of PR; branch staat nog niet op origin.
