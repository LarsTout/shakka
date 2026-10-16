# Wat we leerden over agents en tokens (Shakka v1, 14–16 oktober 2026)

Bedoeld om mee te nemen naar een volgend project. Cijfers komen uit de handbacks van deze sessie (23 work packages, ~110 agent-runs).

## 1. De opzet die werkte

Eén **orchestrator** (de interactieve sessie) die per work package (WP) vier subagents inzet, elk met een eigen model:

| Rol | Model | Taak | Schrijft |
|---|---|---|---|
| architect | Opus | Plan opdelen in WP's met toetsbare acceptatiecriteria; scopewijzigingen verwerken | `WORK_PACKAGES.md`, `STATUS.md` |
| planner | Opus | Blueprint per WP (ontwerp, contracten, testplan) | `docs/wp/WP-XX/blueprint.md` |
| reviewer | Opus | Onafhankelijke review van de blueprint, zonder de redenering van de planner | `review.md` |
| reviewer-light | Sonnet | Zelfde, maar gescoped (ronde 2, S-WP's) | `review.md` |
| builder | Sonnet | Implementeert de goedgekeurde blueprint incl. tests, één commit per stap | code, `deviations.md` |
| verifier | Sonnet | Toetst elk acceptatiecriterium zelf, wijzigt niets | `verification.md` |

Flow per WP: planner → reviewer (max 2 rondes) → builder → verifier (max 2 herstelrondes) → PR → CI → merge. De orchestrator leest alleen samenvattingen en neemt beslissingen; hij schrijft zelf geen blueprint of code.

**Dit was de belangrijkste winst:** de reviewer vond per WP gemiddeld 1 blokkerend punt dat anders in code was beland (offshore-grens 100° i.p.v. 90°, user-id's in request-URL's, een stille faal bij een verkeerde push-sleutel, een maildienst met tracking, een testklok in het verleden). De verifier vond daarnaast echte bugs die de builder had gemist (een SQLSTATE, een crash bij een spot zonder data). Review en verificatie **niet** overslaan.

## 2. Tokenverbruik per rol (gemeten)

| Rol | Per inzet | Aandeel per WP | Opmerking |
|---|---|---|---|
| planner | 200–470k | ~35% | Grootste post. Webonderzoek + blueprints van 600–1100 regels met volledige testcode |
| reviewer ronde 1 | 110–230k | ~20% | Herlas alles en verifieerde bronnen die de planner al had gecheckt |
| planner-revisie | 60–230k | ~10% | |
| reviewer ronde 2 | 60–130k (ongescoped) / **59k** (gescoped, Sonnet) | ~8% | Gescoped en op Sonnet: halve kosten, zelfde oordeel |
| builder | 100–300k | ~17% | Schaalt met aantal bestanden; schreef tests die de planner al had uitgeschreven |
| verifier | 40–100k | ~7% | Lean en effectief |
| architect | 180–470k | eenmalig | |

Totaal per WP vóór de aanpassingen: **0,8–1,2M tokens**. Een dag met 23 WP's: ruwweg 25M subagent-tokens. De orchestrator zelf is klein per beurt, maar een sessie van een dag sleept veel context mee; start voor een nieuwe mijlpaal een verse sessie.

## 3. Wat verspilling was, en de fix

| Verspilling | Fix (sinds PR #31 "lean review") |
|---|---|
| Planner schreef volledige testcode en SQL; builder schreef het opnieuw | Blueprint bevat testnamen + één regel per test; alleen contracten/schema's letterlijk. Streef < 500 regels |
| Reviewer verifieerde externe docs opnieuw | Bronnen die in de blueprint of de projecttabel "gecontroleerd" staan, niet opnieuw checken; alleen bij beveiliging/privacy/geld gericht (max 2) |
| Reviewer gaf 8–13 niet-blokkerende punten | Max 5 (ronde 1), max 3 (ronde 2), één regel elk |
| Ronde 2 herlas de hele blueprint | Alleen de B-punten en de gewijzigde secties; Sonnet (`reviewer-light`) |
| Blokkeren bij een nieuw punt in ronde 2 dat de revisie zelf veroorzaakte | Eén gerichte ronde 3 toestaan als de reviewer een concrete fix geeft |

Verwachte besparing: 40–50% per WP. Eerste meting na de wijziging: reviewer-light ronde 2 in 59k i.p.v. ~110k.

## 4. Wat je in een nieuw project meteen moet regelen

1. **`CLAUDE.md` met harde regels** (budget, privacy, verboden bronnen, niet-configureerbare veiligheidsregels). Elke agent leest het; de reviewer toetst er tegen. Dit vangt de ergste fouten.
2. **Een plan als bron van waarheid** (`PROJECT_PLAN.md`) en een opdeling met toetsbare acceptatiecriteria (`WORK_PACKAGES.md`). "Toetsbaar door een andere agent" is de lat.
3. **Branchmodel met worktrees:** `main` stabiel, `develop` integratie, `wp/WP-XX` per WP in een eigen git-worktree (`.claude/worktrees/WP-XX`). Zo kunnen 2–4 WP's parallel. PR met groene CI als poort; branch protection.
4. **Agentdefinities** uit `.claude/agents/` kopiëren: `planner.md`, `reviewer.md`, `reviewer-light.md`, `builder.md`, `verifier.md`, `architect.md`, plus de skill `.claude/skills/ship/SKILL.md`. Pas alleen de projectregels aan.
5. **Een "Gecontroleerde externe documentatie"-tabel** in WORK_PACKAGES, bijgehouden door architect en planners. Scheelt elke volgende planner en reviewer onderzoek.
6. **Een "Bevestigde beslissingen"-tabel**: elke keuze die de orchestrator namens de eigenaar neemt, met datum. Planners bouwen erop; de eigenaar kan terugdraaien.

## 5. Regels voor de orchestrator

- Geef subagents **absolute paden** naar hun worktree en de regel "schrijf niets buiten deze worktree". Zonder dat schrijven ze in de hoofdcheckout.
- Noem in elke opdracht de 2–3 punten waar extra op gelet moet worden (bekende risico's uit afhankelijke WP's). Geen lange lijsten.
- Neem bij `CHANGES_REQUIRED` zelf de beslissing als de reviewer een keuze voorlegt; geef die letterlijk mee aan de planner.
- Lees van subagents alleen de samenvatting. Nooit het transcript.
- Bewaak per handback de `subagent_tokens`; wijkt een rol structureel af, pas de agentdefinitie aan via een PR.
- Parallelle WP's: laat planners de bestandsnamen van elkaar lezen (alleen lezen) en leg vast wie als eerste merget; wie als tweede merget, rebased en hergebruikt gedeelde helpers.
- Merge-conflicten in `STATUS.md`, RUNBOOK-sectienummers en "beide kanten voegen toe"-bestanden zijn mechanisch; los ze zelf op, niet via een agent.
- Scopewijzigingen (nieuw kanaal, feature schrappen) gaan via de architect, niet via een planner.

## 6. Valkuilen die tijd kostten

- **Docker is in de agent-sandbox niet bereikbaar.** Tests tegen een lokale databasestack moeten in CI (pgTAP in een `db`-job) of door de eigenaar. Plan dat vanaf WP-00 in.
- **De permissieclassifier blokkeert** het aanmaken van accounts namens de eigenaar, repo-instellingen (`gh api`), branch-verwijdering en onbeheerde orchestrators die headless sessies starten. Geef die stappen aan de eigenaar met exacte commando's; probeer geen omweg.
- **Usage-limieten van het abonnement** raken ook subagents: een afgebroken planner laat niets achter. Controleer na een limiet of de worktree leeg is en start opnieuw.
- **Bestandsnaambotsingen bij parallelle WP's** (twee planners kozen dezelfde drie bestandsnamen met andere inhoud). Laat de reviewer ernaar kijken, of geef vooraf een naamprefix per WP.
- **Een branch die vóór een merge van een parallelle WP is afgetakt** loopt achter; rebase vóór de review van ronde 2 en vóór de bouw.
- **"Mini"-testharnassen van de builder** (eigen pgTAP-shim) gaven een vals bewijs; alleen de echte CI telt.
- **Testklokken:** elke test die "nu" gebruikt moet een vaste klok hebben; fixtures in de toekomst verlopen.
- **Lange sessies** worden duur per beurt. Sluit af na een mijlpaal met een `HANDOVER.md` en start vers.

## 7. Wat je kunt weglaten

- Een aparte "nachtorchestrator" die zelf sessies start: wordt geblokkeerd en is onnodig; parallelle `/ship`-sessies met de eigenaar erbij doen hetzelfde.
- Volledige testcode in blueprints.
- Een tweede review voor S-WP's zonder beveiligingsraakvlak: `reviewer-light` ronde 1 volstaat.
- Herverificatie van bronnen die al in de tabel staan.
- Stijlcommentaar in reviews.

## 8. Bestanden om te kopiëren

```
.claude/agents/{architect,planner,reviewer,reviewer-light,builder,verifier}.md
.claude/skills/ship/SKILL.md
.claude/skills/decompose/SKILL.md
CLAUDE.md               (harde regels en werkwijze; projectspecifiek maken)
docs/STATUS.md          (statuslegenda en tabel)
docs/WORK_PACKAGES.md   (alleen de secties "Afspraken die voor alle WP's gelden" als sjabloon)
```
