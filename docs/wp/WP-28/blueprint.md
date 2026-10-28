# Blueprint WP-28: Dependabot
Status: APPROVED
Revisie: 1

## Doel
Dependency- en Actions-updates komen maandelijks als gegroepeerde PR's naar `develop`, zodat de maandcheck van WP-22 (RUNBOOK §18.8 en §18.10) alleen nog reviewt en merget. Dit draait WP-22 A17 ("Geen Dependabot") terug. De SHA-pins van WP-22 blijven, en een test bewaakt ze.

## Aannames
- **A1 (Lars bevestigt).** Lars gaat akkoord met het terugdraaien van WP-22 A17. Dat akkoord staat nog niet in `docs/PROJECT_PLAN.md` of `docs/STATUS.md`; het plan noemt WP-28 alleen als "besluit van Lars". Zonder akkoord stopt de builder.
- **A2. RUNBOOK-sectie.** WORK_PACKAGES_V2 spreekt van "RUNBOOK §17 (maandcheck van WP-22)". In de gemergde RUNBOOK is §17 de sectie van WP-23 (privacy). De maandcheck staat in §18.8 en de dependency-audit in §18.10. AC-2 wordt gelezen als "§18.8 en §18.10".
- **A3. Het SHA-gedrag is geverifieerd** (zie Externe afhankelijkheden). Dependabot werkt een actie die op een SHA staat bij naar de SHA van de nieuwe tag. Het versiecommentaar werkt hij alleen bij als het **op dezelfde regel** staat. Bij alle zes `uses:`-regels in `ci.yml` en `hourly.yml` is dat al zo (`@<sha> # vX.Y.Z`). AC-3 blijft de praktijkcontrole.
- **A4 (Lars bevestigt). Groepen alleen voor minor en patch.** De groep per ecosysteem krijgt `patterns: ["*"]` en `update-types: [minor, patch]`. Een major-update komt als losse PR. Zo houdt één brekende major niet de hele maandgroep tegen. Dit blijft "één `groups`-regel per ecosysteem".
- **A5 (Lars bevestigt). `versioning-strategy: increase-if-necessary` voor `npm` en `uv`.** Een update binnen de grenzen van `package.json` of `pyproject.toml` wijzigt alleen de lockfile; dat is dezelfde regel als RUNBOOK §18.10 ("binnen de grenzen"). Alleen een update buiten de grenzen verruimt de grens in de manifest, en die ziet Lars dan expliciet in de PR. De standaard (`auto`, voor apps `increase`) zou elke maand ook de ondergrenzen in de manifests ophogen.
- **A6. `ignore` voor majors van `@types/node`.** De types volgen Node 24 (`engines`, `.nvmrc`, `NODE_VERSION` in Pages). Een major van `@types/node` hoort bij een Node-upgrade, en dat is geen Dependabot-PR.
- **A7. `target-branch: develop` blijft, zoals de WP voorschrijft**, ook al is `develop` al de default branch (WORK_PACKAGES, "Afspraken"). Gevolg: groepen, `ignore` en `versioning-strategy` gelden niet voor security updates (GitHub-docs). Die komen dus als losse PR's naar de default branch `develop`. Dat is acceptabel.
- **A8. Extra test op het versiecommentaar.** Naast de parse-test van AC-1 komt `test_actions_pins_have_version_comment`. Die toetst dat elke `uses:` het commentaar `# vX[.Y[.Z]]` op dezelfde regel heeft, want Dependabot heeft dat nodig om het commentaar bij te werken. De test kan niet zien of het commentaar bij de SHA hoort; dat blijft een reviewpunt.
- **A9. Cloudflare-builds.** Elke push naar een `dependabot/*`-branch (een nieuwe PR of een rebase) kost een preview-build. De schatting is hoogstens 15 per maand, van de 500 die gratis zijn. Daarom blijven de previews aan: bij de `npm`-PR is de preview nuttig om even te klikken. Komt Builds boven 350, dan sluit Lars `dependabot/*` uit (zie de RUNBOOK-tekst). Dit is een advies; Lars beslist.

## Ontwerp
Eén nieuw bestand `.github/dependabot.yml` met drie `updates`-blokken met dezelfde vorm: maandelijks, naar `develop`, hoogstens 3 open PR's, één groep (`actions`, `web`, `ingest`). Er is geen workflow, geen secret en geen automatisch mergen. Version updates staan aan zodra het bestand op de default branch staat. Alerts en security updates zet Lars aan in de repo-instellingen.

De bewaking zit in `ingest/tests/test_repo_hygiene.py`, dat al de repo-contracten toetst (CI, SHA-pins). Er komen twee tests bij:
1. `test_dependabot_config` parseert het bestand met PyYAML (een runtime-dependency van ingest, er komt dus geen package bij) en toetst de vorm uit AC-1 plus de limiet en de groepsvorm.
2. `test_actions_pins_have_version_comment` (A8).

`test_actions_pinned_to_commit_sha` blijft ongewijzigd. Zet Dependabot een actie op een tag, dan faalt die test op de Dependabot-PR. Dat is bedoeld als signaal.

In de RUNBOOK verandert alleen §18. In de maandchecktabel (punt 8) worden de rijen "Dependencies" en "Actions-pins" vervangen door twee nieuwe rijen ("Dependencies" en "Dependabot-PR's"), en er komt een alinea over Cloudflare onder. Punt 10 wordt "Dependency-updates en -audit": wat Dependabot doet, wat er niet gebeurt (secrets, automatisch mergen), hoe je reviewt, en de handmatige commando's als terugval.

## Bestanden
| Bestand | Actie | Inhoud |
|---|---|---|
| `.github/dependabot.yml` | aanmaken | Exact zoals in Interfaces. |
| `ingest/tests/test_repo_hygiene.py` | wijzigen | `import yaml`; `test_dependabot_config` en `test_actions_pins_have_version_comment`. |
| `docs/RUNBOOK.md` | wijzigen | §18.8: twee rijen en een alinea; §18.10: herschreven (exacte tekst in Interfaces). |
| `docs/STATUS.md` | wijzigen | Zoals gebruikelijk in de `/ship`-flow (status WP-28). |

## Interfaces en contracten

### `.github/dependabot.yml` (exact)
```yaml
# Dependabot version updates (WP-28): monthly, grouped, pull requests against develop.
# Actions stay pinned to a full commit SHA with "# vX.Y.Z" on the same line; Dependabot
# updates both. ingest/tests/test_repo_hygiene.py guards this file and the pins.
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: monthly
    target-branch: develop
    open-pull-requests-limit: 3
    groups:
      actions:
        patterns:
          - "*"
        update-types:
          - minor
          - patch
  - package-ecosystem: npm
    directory: /web
    schedule:
      interval: monthly
    target-branch: develop
    open-pull-requests-limit: 3
    versioning-strategy: increase-if-necessary
    groups:
      web:
        patterns:
          - "*"
        update-types:
          - minor
          - patch
    ignore:
      # Types follow the Node major in engines and .nvmrc; bump them with a Node upgrade.
      - dependency-name: "@types/node"
        update-types:
          - version-update:semver-major
  - package-ecosystem: uv
    directory: /ingest
    schedule:
      interval: monthly
    target-branch: develop
    open-pull-requests-limit: 3
    versioning-strategy: increase-if-necessary
    groups:
      ingest:
        patterns:
          - "*"
        update-types:
          - minor
          - patch
```
Groepsnamen moeten met een letter beginnen en eindigen (GitHub-docs). Gebruik daarom geen cijfers.

### Tests in `ingest/tests/test_repo_hygiene.py`
```python
import yaml  # nieuwe third-party-groep tussen stdlib (re, subprocess) en shakka; ruff/isort

DEPENDABOT_UPDATES = {("github-actions", "/"), ("npm", "/web"), ("uv", "/ingest")}

def test_dependabot_config() -> None: ...
def test_actions_pins_have_version_comment() -> None: ...
```
`test_dependabot_config` toetst, met `data = yaml.safe_load(...)` op `REPO_ROOT / ".github" / "dependabot.yml"`:
- `data["version"] == 2`;
- `len(data["updates"]) == 3`, en de set `(u["package-ecosystem"], u["directory"])` is gelijk aan `DEPENDABOT_UPDATES`;
- per update:
  - `u["schedule"]["interval"] == "monthly"`;
  - `u["target-branch"] == "develop"`;
  - `u["open-pull-requests-limit"] == 3`;
  - `u["groups"]` is een niet-lege `dict`, en elke groep heeft `patterns == ["*"]`.

`test_actions_pins_have_version_comment`:
- loopt over elke regel van `.github/workflows/*.yml` die matcht op `^\s*-?\s*uses:`;
- elke zo'n regel moet fullmatchen op `^\s*-?\s*uses:\s*[\w.-]+/[\w.-]+@[0-9a-f]{40} # v\d+(\.\d+){0,2}\s*$`;
- er is minstens één regel;
- de melding bij falen noemt `bestand:regelnummer`.

### `docs/RUNBOOK.md` §18.8: de rijen "Dependencies" en "Actions-pins" vervangen door
```
   | Dependencies | Security, Dependabot alerts | - | Open alert (high of critical) zonder PR: punt 10, handmatig |
   | Dependabot-PR's | Pull requests, filter `is:open author:app/dependabot` | - | Open PR: reviewen en mergen (punt 10) |
```
Direct onder de alinea over MapTiler, als nieuwe alinea:
```
   Dependabot en Cloudflare: elke push naar een `dependabot/*`-branch (een nieuwe PR of een rebase) is een preview-build. Verwacht wordt hoogstens 15 per maand. Komt Builds boven 350, zet dan in Cloudflare Pages bij de automatische preview-deployments "Custom branches" met include `*` en exclude `dependabot/*`. CI bouwt de web-app toch al.
```

### `docs/RUNBOOK.md` §18.10: volledig vervangen door
```
10. **Dependency-updates en -audit** (Dependabot plus een handmatige terugval; geen CI-stap, niet automatisch mergen).
    - `.github/dependabot.yml` kijkt op de eerste dag van de maand naar `github-actions` (`/`), `npm` (`/web`) en `uv` (`/ingest`). Minor- en patch-updates komen per ecosysteem als één PR naar `develop`; een major komt als losse PR (hoogstens 3 open PR's per ecosysteem). Een update binnen de grenzen van `package.json` of `pyproject.toml` wijzigt alleen de lockfile. Een PR die een grens in de manifest verruimt, verdient extra aandacht. Majors van `@types/node` worden overgeslagen; die horen bij een Node-upgrade.
    - Aanzetten (eenmalig): Settings, Advanced Security: "Dependabot alerts" en "Dependabot security updates" op Enable. Security updates komen los en buiten de maandplanning, als PR naar `develop` (de default branch).
    - Dependabot-PR's krijgen geen Actions-secrets en een `GITHUB_TOKEN` met alleen leesrechten. CI gebruikt geen secrets (§7) en draait dus gewoon. Een merge op `develop` komt pas in productie bij de promotie naar `main`.
    - Reviewen: CI is groen; bij de `npm`-PR de preview kort openen (kaart, inloggen); bij een Actions-PR in de diff controleren dat elke `uses:` op een SHA van 40 tekens staat, met de nieuwe versie als `# vX.Y.Z` op dezelfde regel. Twee tests bewaken de SHA en de vorm van het commentaar, maar niet of het commentaar bij de SHA hoort.
    - Een PR die CI breekt of die je niet wilt: niet mergen. Losse PR: `@dependabot ignore this major version` (of `minor version`, `this dependency`). Gegroepeerde PR: `@dependabot ignore <pakket> minor version` (of `major version`, of alleen `<pakket>`). Terugdraaien: `@dependabot unignore <pakket>`.
    - Handmatig, als terugval of bij twijfel:
      - Web: `cd web && npm audit --omit=dev --audit-level=high`. Los een bevinding op met een minimale update (`npm update <pakket>` of `npm audit fix --omit=dev`, nooit `--force`) en draai daarna `npm run check && npm test && npm run build`.
      - Ingest: `cd ingest && uv export --format requirements-txt --frozen --no-emit-project -o /tmp/shakka-req.txt && uvx pip-audit --require-hashes --disable-pip -r /tmp/shakka-req.txt`. Bij een bevinding: `uv lock --upgrade-package <pakket>` binnen de grenzen van `pyproject.toml`, dan de volledige test.
      - Een SHA-pin zelf bijwerken: zoek de SHA van de release met `gh api repos/<eigenaar>/<repo>/git/ref/tags/<tag> --jq .object.sha`. Is `object.type` "tag", dereferentieer dan met `gh api repos/<eigenaar>/<repo>/git/tags/<sha> --jq .object.sha`. Schrijf de versie als `# vX.Y.Z` op dezelfde regel achter de SHA.
```

## Edge cases
- **E1. Dependabot zet een actie op een tag.** `test_actions_pinned_to_commit_sha` faalt op die PR en die PR wordt niet gemerged. De verifier noteert het, en Lars kiest tussen de test en de config (AC-3).
- **E2. Dependabot werkt de SHA bij, maar het commentaar niet.** De test op het commentaar slaagt (de vorm klopt nog). Dit vang je alleen in de review (RUNBOOK punt 10); de verifier noteert het bij AC-3.
- **E3. Een actie zonder versiecommentaar** (bijvoorbeeld in een latere WP) → `test_actions_pins_have_version_comment` faalt met `bestand:regel`.
- **E4. Een major-update** (bijvoorbeeld `actions/checkout` v8) → een losse PR. Ook die telt mee voor de limiet van 3 open PR's per ecosysteem.
- **E5. Een major van `@types/node`** → er komt geen PR. Minor en patch komen wel mee in de groep `web`.
- **E6. Een update buiten de grens van `pyproject.toml`** (bijvoorbeeld httpx 0.29 bij `<0.29`). Dependabot ziet 0.x→0.29 als minor, dus het zit in de groep en de grens wordt verruimd. Faalt CI, dan: `@dependabot ignore httpx minor version`.
- **E7. Een security-advisory.** Er komt een losse PR naar `develop`, buiten groep, `ignore` en de limiet van 3 (die limiet is daarvoor vast 10). Hetzelfde reviewproces geldt.
- **E8. Twee open Dependabot-PR's raken dezelfde lockfile.** Na de merge van de eerste rebaset Dependabot de tweede. Dat geeft een extra CI-run en een extra preview-build (A9).
- **E9. Een parallelle WP-branch wijzigt `package-lock.json` of `uv.lock`.** Er komt een mergeconflict met een Dependabot-PR. Merge eerst de WP en laat Dependabot daarna rebasen (`@dependabot rebase`).
- **E10. Een ongeldige optie in `dependabot.yml`** (schemafout). De test ziet alleen de vorm. GitHub toont de fout onder Insights, Dependency graph, Dependabot. De verifier controleert dat bij AC-3.
- **E11. Een Dependabot-PR draait CI via `push` en via `pull_request`.** Dat gebeurt nu ook bij `wp/*`-branches, en de minuten zijn onbeperkt (publieke repo). Er hoeft niets te veranderen.
- **E12. Neveneffect van gemergde Dependabot-PR's.** Elke merge is een commit op de default branch `develop`. Dat telt als activiteit voor `check-activity` (WP-11) en houdt de uurlijkse schedule dus mede actief.

## Testplan
| AC | Test | Wat het aantoont | Fixture |
|---|---|---|---|
| AC-1 | `test_dependabot_config` | Het bestand is geldige YAML met `version: 2`, precies de drie paren, en per update `monthly`, `develop`, limiet 3 en niet-lege groepen met `patterns: ["*"]`. | Het echte `.github/dependabot.yml` |
| AC-1 (A8) | `test_actions_pins_have_version_comment` | Elke `uses:` in de workflows heeft een SHA van 40 tekens met `# vX.Y.Z` op dezelfde regel. | Het echte `ci.yml` en `hourly.yml` |
| AC-1 | `test_actions_pinned_to_commit_sha` (bestaand) | Blijft groen; ongewijzigd. | Idem |
| AC-2 | Geen automatische test | De verifier leest §18.8 (rij "Dependabot-PR's" en de Cloudflare-alinea) en §18.10. | – |
| AC-3 | Handmatig, `NEEDS_LARS` | Na de merge en het aanzetten: per ecosysteem een geslaagde controle onder Insights, Dependency graph, Dependabot. Een eventuele `github-actions`-PR houdt de SHA met een kloppend `# vX.Y.Z` (E1, E2). | – |

Even zelf controleren (de testcode wordt niet gecommit):
- verwijder tijdelijk `target-branch` uit één update → `test_dependabot_config` faalt;
- haal tijdelijk `# v7.0.1` weg uit `ci.yml` → `test_actions_pins_have_version_comment` faalt.

## Externe afhankelijkheden
Er komt geen nieuw package bij. `pyyaml>=6.0.3,<7` staat al in `ingest/pyproject.toml`.

| Onderwerp | Bevinding | Bron | Status |
|---|---|---|---|
| Ecosysteemwaarden | `github-actions`, `npm` en `uv` zijn geldig | WORK_PACKAGES_V2, tabel "Gecontroleerde externe documentatie" | Overgenomen |
| SHA-pin en commentaar | "Dependabot updates the version documentation of GitHub Actions when the comment is on the same line"; een commit zonder tag wordt bijgewerkt naar de laatste commit. Changelog 31 okt. 2022: Dependabot werkt de semver in het commentaar bij als een actie op een SHA staat. | https://docs.github.com/en/code-security/dependabot/ecosystems-supported-by-dependabot/supported-ecosystems-and-repositories, https://github.blog/changelog/2022-10-31-dependabot-now-updates-comments-in-github-actions-workflows-referencing-action-versions/ | Zelf gecontroleerd, 28 okt. 2026 |
| Map `/` voor actions | `directory: "/"` controleert `.github/workflows` | https://docs.github.com/en/code-security/dependabot/working-with-dependabot/keeping-your-actions-up-to-date-with-dependabot | Zelf gecontroleerd |
| `target-branch` | Alleen manifests op die branch tellen voor version updates. Security updates gebruiken altijd de default branch, en de opties van dat ecosysteem gelden er dan niet voor. | https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference | Zelf gecontroleerd |
| `schedule` | `monthly` = de eerste dag van de maand; zonder `time` een willekeurig tijdstip (UTC) | Idem | Zelf gecontroleerd |
| `open-pull-requests-limit` | Standaard 5, alleen voor version updates. Security updates hebben een vaste limiet van 10. | Idem | Zelf gecontroleerd |
| `groups` | `patterns` (met `*`), `update-types` (`minor`, `patch`, `major`), `applies-to` standaard `version-updates`. Wat niet in een groep valt, wordt een losse PR. De naam begint en eindigt met een letter. | Idem | Zelf gecontroleerd |
| `versioning-strategy` | Ondersteund door onder andere `npm` en `uv`. `increase-if-necessary` laat de eis staan als de nieuwe versie erin past en verruimt hem anders. De standaard `auto` is `increase` voor apps. | Idem | Zelf gecontroleerd. Per waarde is de ondersteuning voor `uv` niet apart vermeld (R2). |
| `ignore` | `dependency-name` plus `update-types: [version-update:semver-major]` | Idem | Zelf gecontroleerd |
| `uv` | Ecosysteem `uv`, "supported version v0.11"; version updates en security updates worden ondersteund | supported-ecosystems-and-repositories (zie boven) | Zelf gecontroleerd |
| Secrets bij Dependabot-runs | Runs vanuit `push` en `pull_request` werken als een fork: `GITHUB_TOKEN` alleen-lezen, geen Actions-secrets, alleen Dependabot-secrets | https://docs.github.com/en/code-security/dependabot/troubleshooting-dependabot/troubleshooting-dependabot-on-github-actions | Zelf gecontroleerd |
| Security updates aanzetten | Settings, "Security and quality", Advanced Security, "Dependabot security updates", Enable. Geef geen `target-branch` op voor een security-updateconfig. | https://docs.github.com/en/code-security/dependabot/dependabot-security-updates/configuring-dependabot-security-updates | Zelf gecontroleerd |
| Commentaarcommando's | Losse PR: `@dependabot ignore this major/minor/patch version`, `this dependency`, `rebase`, `recreate`. Groep: `@dependabot ignore <naam> [major/minor/patch version]`, `unignore <naam>`. | https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-pull-request-comment-commands | Zelf gecontroleerd |
| Cloudflare Pages-branches | Bij "Custom branches" gaan excludes vóór includes, wildcard `*`. Het voorbeeld uit de docs is exclude `dependabot/*` met include `*`. | https://developers.cloudflare.com/pages/configuration/branch-build-controls/ | Zelf gecontroleerd |
| Default label | `dependencies` | https://docs.github.com/en/code-security/dependabot/working-with-dependabot/managing-pull-requests-for-dependency-updates | Zelf gecontroleerd (niet gebruikt in het filter) |

## Risico's
- **R1. Een bekende bug: Dependabot laat het commentaar soms staan** (dependabot-core #8127, bij YAML-strings tussen aanhalingstekens). Onze `uses:`-waarden staan niet tussen aanhalingstekens. Restrisico via E2 en AC-3.
- **R2. `uv` en `increase-if-necessary`.** De docs noemen `uv` alleen als ecosysteem dat `versioning-strategy` ondersteunt, zonder tabel per waarde. Wijst GitHub de waarde af (E10), dan haalt de builder of verifier de regel weg bij `uv` (standaardgedrag) en noteert dat in `deviations.md`.
- **R3. De ondersteunde uv-versie heet in de docs "v0.11"**; de lockfile is `revision = 5`. Faalt de uv-update met een lockfile-fout, dan ziet de verifier dat bij AC-3 en beslist Lars. `uv.lock` handmatig blijft dan de terugval (§18.10).
- **R4. Reviewlast.** Dat zijn drie groeps-PR's per maand, plus majors en security updates. De limiet van 3 per ecosysteem begrenst de version updates.
- **R5. Een gemergde update breekt productie pas bij de promotie naar `main`.** De uurlijkse run draait `main`. Lars test `develop` vóór de promotie, zoals nu al.

## Buiten scope
- `npm audit` of `pip-audit` als CI-stap, of als geplande workflow (WP-22 A17; WORK_PACKAGES_V2 "Geoogst").
- Automatisch mergen, `cooldown` (de standaard van 3 dagen blijft), `commit-message`, eigen labels.
- Versiegrenzen in `pyproject.toml` en `package.json` wijzigen.
- Cloudflare-instellingen wijzigen. Dat is advies in de RUNBOOK, en Lars beslist (A9).
- Verouderde verwijzingen `§17.1` en `§17.3` in RUNBOOK §13.1 (die horen naar §18 te wijzen). Een kleine losse docs-fix; de orchestrator kan die meenemen.

## Gevolgen voor latere WP's
- Een nieuwe `uses:` in een workflow staat op een SHA van 40 tekens met `# vX.Y.Z` op dezelfde regel. Anders faalt CI (twee tests).
- Een nieuwe map met een manifest (een tweede npm- of Python-project) krijgt een eigen `updates`-blok, en de builder werkt `DEPENDABOT_UPDATES` bij.
- WP-branches die `package-lock.json` of `uv.lock` wijzigen, kunnen botsen met open Dependabot-PR's (E9). Merge eerst de WP en laat Dependabot daarna rebasen.
- WP-22 A17, R8 en "Buiten scope" (Dependabot) zijn hiermee achterhaald. Dat staat vanaf nu in RUNBOOK §18.10.

## Stappenplan voor de builder
1. **Controleer A1.** Is het akkoord van Lars op het terugdraaien van WP-22 A17 er niet, stop dan en meld het.
2. Maak `.github/dependabot.yml` exact zoals in Interfaces. Voeg `import yaml`, `DEPENDABOT_UPDATES` en `test_dependabot_config` toe. Daarna is `cd ingest && uv run pytest tests/test_repo_hygiene.py` groen. Doe de mutatiecheck uit het testplan (tijdelijk `target-branch` weghalen).
3. Voeg `test_actions_pins_have_version_comment` toe. De test is groen op de huidige workflows; doe de mutatiecheck (tijdelijk een commentaar weghalen) en draai die terug.
4. RUNBOOK: in §18.8 de twee rijen vervangen en de Cloudflare-alinea toevoegen, §18.10 volledig vervangen, beide letterlijk volgens Interfaces.
5. `cd ingest && uv run ruff check . && uv run ruff format --check . && uv run pytest`: alles groen.
6. Zet in `pr.md` onder "Nodig van Lars":
   - na de merge naar `develop`: Settings, Advanced Security, "Dependabot alerts" en "Dependabot security updates" op Enable;
   - daarna de controle van AC-3: Insights, Dependency graph, Dependabot, met per ecosysteem een geslaagde controle, en bij de eerste Actions-PR SHA plus commentaar (E1, E2);
   - eventueel nu al "Check for updates" per ecosysteem in die tab, om niet tot de eerste van de maand te wachten.
