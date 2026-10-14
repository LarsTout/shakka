---
description: Deel docs/PROJECT_PLAN.md op in work packages met acceptatiecriteria. Eenmalig aan het begin, of opnieuw na een scopewijziging.
model: sonnet
disable-model-invocation: true
---

Je bent de orchestrator. Doe het werk niet zelf; delegeer.

1. Check of `docs/WORK_PACKAGES.md` al bestaat. Zo ja: vraag Lars of hij de opdeling opnieuw wil maken en stop tot hij antwoordt.
2. Delegeer aan de **architect** subagent: "Deel `docs/PROJECT_PLAN.md` op volgens je instructies. Extra context van Lars: $ARGUMENTS"
3. Lees daarna alleen de samenvatting van de architect en de tabel in `docs/STATUS.md`.
4. Geef Lars:
   - het aantal WP's per mijlpaal
   - de afwijkingen van het plan
   - wat hij moet aanleveren voor WP-00 (accounts, keys)
   - de vraag: "Akkoord met de opdeling? Dan zet ik STATUS op goedgekeurd en kun je starten met `/ship WP-00`."
5. Pas na expliciet akkoord: vervang in `docs/STATUS.md` de regel `Opdeling: wacht op akkoord van Lars.` door `Opdeling: goedgekeurd.` en commit `docs: approve work package decomposition`.
