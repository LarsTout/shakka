---
description: Bouw één work package van blueprint tot gemergde code. Planner, onafhankelijke review, builder en verifier, elk als eigen subagent.
argument-hint: WP-XX
model: sonnet
disable-model-invocation: true
---

Je bent de orchestrator voor work package **$0**. Je schrijft zelf geen blueprint, review of code: je delegeert aan subagents, geeft ze alleen paden en het WP-ID, en houdt je eigen context klein. Lees van subagents alleen hun samenvatting en het oordeel bovenaan hun bestand.

Map van deze WP: `docs/wp/$0/`. Werk `docs/STATUS.md` bij bij elke statuswissel.

## 0. Check
- `docs/STATUS.md` bevat `Opdeling: goedgekeurd.` Anders stop: "Draai eerst `/decompose`."
- $0 bestaat in `docs/WORK_PACKAGES.md`.
- Alle WP's waar $0 van afhangt staan op `done`. Anders stop en noem welke ontbreken.
- Staat $0 al op een latere status, ga dan verder vanaf die stap (hervatten).
- Staat er bij $0 "Nodig van Lars" iets dat nog niet geregeld is (bijv. een key in `.env`)? Vraag het nu, voordat er werk gebeurt.

## 1. Blueprint
Status `blueprint`. Delegeer aan **planner**: "Schrijf de blueprint voor $0."

## 2. Onafhankelijke review (max 2 rondes)
Status `in_review`. Delegeer aan **reviewer**: "Review de blueprint van $0." Geef géén samenvatting van de planner mee.
- `APPROVED`: zet in `blueprint.md` de regel `Status: DRAFT` op `Status: APPROVED`, status `approved`, commit `docs($0): approved blueprint`.
- `CHANGES_REQUIRED` in ronde 1: delegeer aan **planner**: "Herzie de blueprint van $0 op basis van `docs/wp/$0/review.md`." Daarna opnieuw de **reviewer** (nieuwe instantie, ronde 2).
- `CHANGES_REQUIRED` in ronde 2: status `blocked`, stop. Geef Lars de openstaande blokkerende punten en vraag hoe verder.

## 3. Bouwen
- Check dat de working tree schoon is en dat je op `main` zit. Maak branch `wp/$0` (of ga erop verder als die bestaat).
- Status `building`. Delegeer aan **builder**: "Implementeer de goedgekeurde blueprint van $0."
- `BLOCKED`: status `blocked`, stop, geef Lars de reden uit `deviations.md`.

## 4. Verificatie (max 2 herstelrondes)
Status `verifying`. Delegeer aan **verifier**: "Verifieer $0."
- `PASS`: ga naar stap 5.
- `NEEDS_LARS`: stop en vertel Lars precies wat er nodig is. Na zijn actie: opnieuw de verifier.
- `FAIL`: delegeer aan **builder**: "Los de problemen uit `docs/wp/$0/verification.md` op." Daarna opnieuw de **verifier**. Na de tweede `FAIL`: status `blocked`, stop, geef Lars de problemen.

## 5. Afronden
- `git checkout main && git merge --ff-only wp/$0`. Lukt fast-forward niet: stop en vraag Lars.
- Status `done`, commit `docs($0): done`.
- Geef Lars maximaal 8 regels: wat er nu werkt, hoe hij het zelf kan proberen (concreet commando), eventuele niet-blokkerende reviewpunten die later opgepakt kunnen worden, en welke WP logisch de volgende is.
- Zeg dat hij voor de volgende WP een nieuwe sessie start.
