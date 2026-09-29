# Supplychainer Bug-Fix Report

## Scope

This version fixes the original routing/threat-intelligence defects identified during the baseline audit. No new product feature work was added.

## Semantic decision

`SUEZ_BLOCK` is treated as a **physical closure**. All routing personas must avoid `CHOKE-SUEZ` when the scenario is active.

## Confirmed/fixed issues

1. **CARF modal relevance inversion** — relevant sea/air signals were discarded while unrelated modal signals passed through. CARF now preserves matching-mode signals and rejects explicitly other-mode signals across air/sea/rail/road. Token matching prevents `airport` from being interpreted as `port`.
2. **Contrastive NLP score inversion** — positive disaster-vs-safe margins were previously zeroed. Positive margins above the noise floor now produce a bounded positive threat score.
3. **Scenario ETA/cost audit inconsistency** — scenario delay was added to route ETA and then added again in the audit trace; an unexplained 10% scenario cost was also recorded despite not being part of total cost. Scenario delay is now isolated in its own audit bucket and no invented scenario cost is added.
4. **Inference failure became zero delay** — predictor failures now use a conservative mode prior and explicitly mark the result as non-defensible instead of returning an optimistic zero.
5. **Warmup false readiness** — background warmup now fails if the predictor or NLP engine did not actually become ready.
6. **Shared scenario state** — routing now uses request-local scenario lookups instead of mutating one global active scenario during route calculation.
7. **SUEZ_BLOCK did not block Suez** — the blocked physical hub is removed from each persona's routing graph before Dijkstra, so no persona can route through it.
8. **Forensic explanation contained invented numbers** — explanations now use actual route ETA, cost, threat, transfers, and scenario delay.
9. **Internal routing errors were reported as no-route** — internal errors are retained and surfaced distinctly when no candidate can be produced.

## Verification

Official regression suite:

- **18 passed, 0 failed** (`pytest -q`)
- Tests are collected only from `tests/`; legacy `scratch/` scripts are not part of the regression suite.

### Real routing scenario

Shanghai -> Rotterdam, STRICT:

| Preference | Scenario | Result | ETA (h) | Cost | Threat | Suez? |
|---|---|---|---:|---:|---:|---|
| any | none | Balanced route through Suez is available | 409.9 | 2603.67 | 0.05 | Yes |
| any | SUEZ_BLOCK | Alternative route | 692.0 | 4084.45 | 0.05 | No |
| sea | none | Direct sea route through Suez | 413.9 | 2565.33 | 0.05 | Yes |
| sea | SUEZ_BLOCK | Cape-style alternative | 695.9 | 4046.11 | 0.05 | No |

The API integration test also returns HTTP 200 and no `CHOKE-SUEZ` leg for the SUEZ_BLOCK sea request.

## Remaining limitation

The current environment does not have `sentence_transformers` installed, so the background NLP warmup correctly reports failure rather than pretending the intelligence layer is ready. The regression suite uses deterministic mocked NLP embeddings. The real MiniLM/Hugging Face runtime should be verified on the development laptop after installing the repository requirements.
