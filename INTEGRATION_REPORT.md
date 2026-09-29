# Supplychainer Feature Integration Report

## Baseline

The integration starts from the verified bug-fixed repository. Existing SUEZ_BLOCK semantics remain a physical closure.

## Integrated workstreams

- Member 1: live quantile-risk integration. The supplied production artifact exposes a genuine P85 model; P50/P95 remain null rather than being fabricated. P85 is applied to meaningful disruption signals during route scoring.
- Member 2: structured threat/route explainability, merged into the ML-enabled route recommender.
- Member 3: API-backed interactive SVG multimodal network map and route highlighting. The frontend consumes `/api/network`; it does not hardcode the topology.
- Member 4: SQLite route history, CSV audit export, and deterministic scenario-based route alerts.

## Shared-file merges

`backend/engine/route_recommender.py` and `backend/main.py` were manually merged because Members 1/2 and Members 3/4 both modified them.

The merge preserves:

- bug-fix routing semantics;
- live P85 scoring;
- route explanations;
- physical network projection;
- history/CSV endpoints;
- alert endpoint.

## Verification

Backend/regression suite:

    33 passed

The API was also exercised with a TestClient in offline mode. `POST /api/recommend` returned HTTP 200 for Shanghai -> Rotterdam with `SUEZ_BLOCK`, and the returned recommendations contained no `CHOKE-SUEZ` leg. `/api/history`, `/api/alerts`, and `/api/network` also returned successful responses.

The frontend source is integrated. A production Vite build could not be completed in the sandbox because the supplied `node_modules` bundle is incomplete (`vite/bin/vite.js` is missing), and outbound package installation is unavailable. Run `npm install` followed by `npm run build` in a normal development environment.
