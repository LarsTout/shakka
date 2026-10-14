---
description: Bouw één work package van blueprint tot gemergde code. Planner, onafhankelijke review, builder en verifier, elk als eigen subagent.
argument-hint: WP-XX
model: sonnet
disable-model-invocation: true
---

Je bent de orchestrator voor work package **$0**. Je schrijft zelf geen blueprint, review of code: je delegeert aan subagents, geeft ze alleen paden en het WP-ID, en houdt je eigen context klein. Lees van subagents alleen hun samenvatting en het oordeel bovenaan hun bestand.

Map van deze WP: `docs/wp/$0/`. Werk `docs/STATUS.md` bij bij elke statuswissel en commit die wissel op de WP-branch.

## Branchmodel
- `main` is stabiel. Lars promoot `develop` naar `main` per mijlpaal; jij raakt `main` nooit aan.
- `develop` is de integratiebranch. Elke WP werkt op een eigen branch `wp/$0`, afgetakt van `origin/develop`, en komt via een pull request met groene CI terug op `develop`.
- Meerdere WP's kunnen tegelijk draaien, elk in een eigen sessie en een eigen git-worktree.

## 0. Check
- `git fetch origin` en lees `docs/STATUS.md` van `origin/develop` (`git show origin/develop:docs/STATUS.md`). Die bevat `Opdeling: goedgekeurd.` Anders stop: "Draai eerst `/decompose`."
- $0 bestaat in `docs/WORK_PACKAGES.md`.
- Alle WP's waar $0 van afhangt staan op `done` in die STATUS. Anders stop en noem welke ontbreken.
- Staat $0 al op een latere status, ga dan verder vanaf die stap (hervatten).
- Staat er bij $0 "Nodig van Lars" iets dat nog niet geregeld is (bijv. een key in `.env`)? Vraag het nu, voordat er werk gebeurt.

## 0b. Werkmap
- Bestaat branch `wp/$0` nog niet: `git worktree add .claude/worktrees/$0 -b wp/$0 origin/develop`. Bestaat hij wel (hervatten): `git worktree add .claude/worktrees/$0 wp/$0` (of sla over als de worktree er al is).
- Zet de gitignored lokale bestanden in de worktree: `ln -sf "$(git rev-parse --show-toplevel)/.env" .claude/worktrees/$0/.env`, en kopieer `supabase/.temp/` als die bestaat.
- Ga met `EnterWorktree` (parameter `path`) naar `.claude/worktrees/$0`. Alles hierna gebeurt daar; subagents erven die werkmap.

## 1. Blueprint
Status `blueprint`. Delegeer aan **planner**: "Schrijf de blueprint voor $0."

## 2. Onafhankelijke review (max 2 rondes)
Status `in_review`. Delegeer aan **reviewer**: "Review de blueprint van $0." Geef géén samenvatting van de planner mee.
- `APPROVED`: zet in `blueprint.md` de regel `Status: DRAFT` op `Status: APPROVED`, status `approved`, commit `docs($0): approved blueprint`.
- `CHANGES_REQUIRED` in ronde 1: delegeer aan **planner**: "Herzie de blueprint van $0 op basis van `docs/wp/$0/review.md`." Daarna opnieuw de **reviewer** (nieuwe instantie, ronde 2).
- `CHANGES_REQUIRED` in ronde 2: status `blocked`, stop. Geef Lars de openstaande blokkerende punten en vraag hoe verder.

## 3. Bouwen
- Check dat de working tree schoon is en dat je op `wp/$0` zit.
- Status `building`. Delegeer aan **builder**: "Implementeer de goedgekeurde blueprint van $0."
- `BLOCKED`: status `blocked`, stop, geef Lars de reden uit `deviations.md`.

## 4. Verificatie (max 2 herstelrondes)
Status `verifying`. Delegeer aan **verifier**: "Verifieer $0."
- `PASS`: ga naar stap 5.
- `NEEDS_LARS`: stop en vertel Lars precies wat er nodig is. Na zijn actie: opnieuw de verifier.
- `FAIL`: delegeer aan **builder**: "Los de problemen uit `docs/wp/$0/verification.md` op." Daarna opnieuw de **verifier**. Na de tweede `FAIL`: status `blocked`, stop, geef Lars de problemen.

## 5. Afronden
- Status `done`, commit `docs($0): done`.
- `git fetch origin && git rebase origin/develop`. Conflict: stop en vraag Lars; los het niet zelf op.
- `git push -u origin wp/$0`.
- Maak de PR: `gh pr create --base develop --head wp/$0 --title "$0: <naam uit STATUS>" --body-file docs/wp/$0/pr.md`. Schrijf `pr.md` zelf: wat er nu werkt, hoe Lars het probeert, niet-blokkerende reviewpunten, en de afsluitregel `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- Wacht op CI: `gh pr checks --watch --fail-fast`. Rood: delegeer aan **builder**: "CI faalt op de PR van $0; los het op." Commit, push, opnieuw wachten. Na de tweede rode run: status `blocked`, stop, geef Lars de link naar de run.
- Groen: `gh pr merge --merge --delete-branch`. Lukt dat niet (conflict, review vereist): stop en geef Lars de PR-link.
- Verlaat de worktree met `ExitWorktree` (opruimen) en `git worktree prune`.
- Geef Lars maximaal 8 regels: de PR-link, wat er nu werkt, hoe hij het zelf kan proberen (concreet commando, vanaf `develop`), eventuele niet-blokkerende reviewpunten, en welke WP logisch de volgende is.
- Zeg dat hij voor de volgende WP een nieuwe sessie start.
