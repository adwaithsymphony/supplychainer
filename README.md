# Supplychainer

> **AI-powered multimodal supply-chain risk intelligence and routing
> command console.**

Supplychainer turns a conventional route request into a risk-aware
logistics decision. It combines a canonical global multimodal network,
live/derived disruption signals, Context-Aware Relevance Filtering
(CARF), contrastive NLP, quantile ML risk prediction, scenario
simulation, route explainability, alerts, history, and an executive
React dashboard.

------------------------------------------------------------------------

## What Supplychainer Does

A typical request looks like:

**Shanghai → Rotterdam**

The system can:

1.  Resolve the requested locations to canonical logistics hubs.
2.  Build multimodal route candidates across sea, rail, road, and air.
3.  Ingest disruption information and evaluate its relevance.
4.  Apply **CARF** so irrelevant disruptions do not automatically
    contaminate a route.
5.  Score meaningful threats with the NLP engine.
6.  Apply the ML risk model and expose the **P85 worst-case delay
    estimate** when a meaningful disruption signal exists.
7.  Recalculate routes under operational scenarios such as a Suez Canal
    blockage.
8.  Return multiple route personas such as **FASTEST** and **BALANCED**.
9.  Explain why a route was selected.
10. Record route history and generate deterministic alerts.
11. Visualize the network and selected route in the command dashboard.

------------------------------------------------------------------------

## Architecture

``` text
                    ┌─────────────────────────┐
                    │   React / Vite Dashboard │
                    │  Executive Command UI    │
                    └────────────┬────────────┘
                                 │
                         HTTP / WebSocket
                                 │
                    ┌────────────▼────────────┐
                    │      FastAPI Backend     │
                    │       backend/main.py    │
                    └────────────┬────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
          ▼                      ▼                      ▼
   Multimodal Network      Threat Intelligence     Scenarios
   + Route Recommender     + CARF + NLP + ML       + Alerts
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 ▼
                       Explainability / History
```

### Core components

  -----------------------------------------------------------------------------
  Component                                 Purpose
  ----------------------------------------- -----------------------------------
  `backend/main.py`                         FastAPI application and live API
                                            entry point

  `backend/engine/multimodal_network.py`    Canonical multimodal logistics
                                            graph

  `backend/engine/route_recommender.py`     Route generation, persona
                                            selection, ML-aware weighting

  `backend/engine/threat_intelligence.py`   NLP, CARF, threat scoring, quantile
                                            ML prediction

  `backend/engine/scenario_manager.py`      Deterministic disruption scenarios

  `backend/engine/explainability.py`        Structured route/threat
                                            explanations

  `backend/engine/alert_engine.py`          Scenario-aware route alerts

  `backend/engine/history_store.py`         Local route recommendation history

  `backend/engine/audit_export.py`          Audit/history export support

  `frontend/src/RouteRecommender.jsx`       Main command-console workflow

  `frontend/src/NetworkMap.jsx`             Multimodal network visualization
  -----------------------------------------------------------------------------

------------------------------------------------------------------------

# Quick Start

## Requirements

Recommended:

-   Windows, Linux, or macOS
-   Python 3.13
-   Node.js + npm
-   Internet connection for the first Hugging Face model download

The backend can run on a **CPU-only machine**. If CUDA is available, the
NLP model can use it automatically.

------------------------------------------------------------------------

# 1. Clone the repository

``` bash
git clone <YOUR_GITHUB_REPO_URL>
cd Supplychainer
```

Or download the repository ZIP and open a terminal in its root
directory.

**Important:** run the backend from the **project root**, not from
inside `backend/`.

You should be in a directory containing:

``` text
backend/
frontend/
Execution/
requirements.txt
README.md
```

------------------------------------------------------------------------

# 2. Backend Setup

Create a virtual environment:

### Windows

``` bat
python -m venv .venv
.venv\Scripts\activate
```

### Linux / macOS

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

Install Python dependencies:

``` bash
python -m pip install -r requirements.txt
```

Start FastAPI:

``` bash
python -m uvicorn backend.main:app --reload
```

The backend will normally be available at:

``` text
http://127.0.0.1:8000
```

FastAPI interactive documentation:

``` text
http://127.0.0.1:8000/docs
```

### First startup

The first startup may download the `all-MiniLM-L6-v2` Sentence
Transformer model from Hugging Face. This can take a few minutes
depending on the connection.

A successful startup should eventually show:

``` text
Supplychainer Engine Active: Canonical Global Registry Loaded.
[NLP ENGINE] Starting warmup...
NLP Brain: Loaded Historical Anchor Matrix.
[WARMUP] Unified Calibration Complete.
```

Keep this terminal running.

------------------------------------------------------------------------

# 3. Frontend Setup

Open a **second terminal**.

Go to the frontend:

``` bat
cd frontend
```

Install JavaScript dependencies:

``` bat
npm install
```

Start the development server:

``` bat
npm run dev
```

Vite will display a local URL, normally:

``` text
http://localhost:5173/
```

Open that URL in your browser.

------------------------------------------------------------------------

# 4. Verify the Installation

## Backend tests

From the project root:

``` bash
pytest -q
```

The integrated version includes regression coverage for:

-   routing
-   scenarios
-   CARF
-   NLP
-   ML routing
-   explainability
-   history
-   alerts
-   API behavior

## Frontend production build

From `frontend/`:

``` bash
npm run build
```

A successful build ends with a Vite message similar to:

``` text
built in ...s
```

The project may report a warning about a JavaScript chunk being larger
than 500 kB. This is a Vite optimization warning, not a build failure.

------------------------------------------------------------------------

# Using the Dashboard

## Basic route

1.  Start the backend.
2.  Start the frontend.
3.  Open the dashboard.
4.  Select an **Origin Hub**.
5.  Select a **Destination Hub**.
6.  Choose a transport mode or leave it **Unconstrained**.
7.  Select the routing policy.
8.  Leave **Operational Configuration** as `Operational Normal`.
9.  Click **Generate Strategic Route Options**.

A useful first test is:

``` text
Origin:      Port of Shanghai
Destination: Port of Rotterdam
Mode:        Unconstrained
Policy:      STRICT
Scenario:    Operational Normal
```

The dashboard should display route candidates, the selected backend
route, ETA/cost/risk information, the network visualization, and the
decision audit.

------------------------------------------------------------------------

# Scenario Demonstration

Supplychainer includes deterministic disruption scenarios for repeatable
demonstrations.

Available scenario IDs include:

  ID                       Scenario
  ------------------------ --------------------------
  `SUEZ_BLOCK`             Suez Canal Blockage
  `RED_SEA_CONFLICT`       Red Sea Escalation
  `LA_PORT_STRIKE`         LA Port Strike
  `CHENNAI_FLOOD`          Chennai Monsoon Flooding
  `DUBAI_AIR_CONGESTION`   Dubai Hub Surge
  `HORMUZ_CLOSURE`         Hormuz Strait Escalation

The frontend loads these directly from:

``` text
GET /api/scenarios
```

### Recommended demo

Use:

``` text
Origin:      Port of Shanghai
Destination: Port of Rotterdam
Scenario:    Suez Canal Blockage
Policy:      STRICT
```

Then generate the route again.

The Suez scenario marks `CHOKE-SUEZ` as closed. The route engine should
therefore select an alternative path rather than silently routing
through the blocked chokepoint.

The dashboard should update:

-   selected route
-   ETA
-   cost
-   threat/risk information
-   scenario impact
-   affected legs
-   route explanation
-   network visualization

------------------------------------------------------------------------

# Understanding the ML / P85 Output

Supplychainer uses a quantile ML risk model to estimate a **P85
worst-case delay buffer**.

The frontend displays the model's P85 output when a meaningful
disruption signal exists.

P85 should **not** be interpreted as a guaranteed delay.

Also, the application does not fabricate P50/P95 values when they are
unavailable. The integrated risk engine exposes the model-supported P85
result.

A route can legitimately report no meaningful disruption / no P85
increment when the traversable route has no qualifying disruption
signal.

------------------------------------------------------------------------

# API Endpoints

The live application is served from `backend/main.py`.

Important endpoints:

  Method   Endpoint                   Purpose
  -------- -------------------------- ---------------------------------------------
  `GET`    `/api/status`              Engine status
  `GET`    `/api/scenarios`           Available disruption scenarios
  `GET`    `/api/hubs`                Canonical hub registry
  `GET`    `/api/hubs/search?q=...`   Search hubs
  `GET`    `/api/network`             Physical network topology for the dashboard
  `GET`    `/api/cities`              City-to-hub mapping
  `POST`   `/api/recommend`           Generate route recommendations
  `GET`    `/api/history`             Route recommendation history
  `GET`    `/api/history/export`      Export history/audit data
  `POST`   `/api/alerts`              Evaluate route alerts
  `GET`    `/docs`                    FastAPI Swagger UI
  `WS`     `/ws`                      Engine status stream

Example request:

``` json
{
  "source": "Shanghai",
  "destination": "Rotterdam",
  "cargo_type": "general",
  "priority": "normal",
  "budget_sensitivity": "medium",
  "transport_preference": "any",
  "routing_policy": "STRICT",
  "scenario": "SUEZ_BLOCK"
}
```

------------------------------------------------------------------------

# Project Structure

``` text
Supplychainer/
│
├── backend/
│   ├── main.py
│   ├── engine/
│   │   ├── route_recommender.py
│   │   ├── threat_intelligence.py
│   │   ├── multimodal_network.py
│   │   ├── scenario_manager.py
│   │   ├── explainability.py
│   │   ├── alert_engine.py
│   │   ├── history_store.py
│   │   └── audit_export.py
│   └── data/
│
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   └── src/
│       ├── App.jsx
│       ├── RouteRecommender.jsx
│       ├── NetworkMap.jsx
│       ├── SupplierIntelligence.jsx
│       └── BenchmarkCharts.jsx
│
├── Execution/
│   ├── risk_model.pkl
│   ├── label_encoders.pkl
│   ├── nlp_anchors.pt
│   └── calibration_profiles.json
│
├── tests/
├── benchmarks/
├── Code/
├── scratch/
├── requirements.txt
├── LICENSE
└── README.md
```

`backend/main.py` is the live FastAPI entry point.

------------------------------------------------------------------------

# CPU / Windows Notes

Supplychainer can run without an NVIDIA GPU.

The NLP engine selects CUDA when it is available and falls back to CPU
otherwise. The precomputed NLP anchor file is also loaded with CPU-safe
mapping.

On Windows, `uvloop` is not required because the standard Uvicorn event
loop is used.

If your `requirements.txt` contains:

``` text
uvloop==0.22.1
```

change it to:

``` text
uvloop==0.22.1; platform_system != "Windows"
```

This allows Linux/macOS installations to use `uvloop` while preventing
Windows installation failures.

------------------------------------------------------------------------

# Common Problems

### `'uvicorn' is not recognized`

Use:

``` bash
python -m uvicorn backend.main:app --reload
```

instead of calling `uvicorn` directly.

### `No module named ...`

Make sure the virtual environment is active and run:

``` bash
python -m pip install -r requirements.txt
```

### `uvloop does not support Windows`

Use the platform-specific dependency line:

``` text
uvloop==0.22.1; platform_system != "Windows"
```

Then reinstall dependencies.

### NLP model download on first launch

The first launch may download the Hugging Face Sentence Transformer
model. This is expected.

An optional Hugging Face token can be configured through the `HF_TOKEN`
environment variable if higher Hub rate limits are required.

### Frontend says "Engine connection failed"

Make sure both processes are running:

**Terminal 1:**

``` bash
python -m uvicorn backend.main:app --reload
```

**Terminal 2:**

``` bash
cd frontend
npm run dev
```

Then open the Vite URL.

------------------------------------------------------------------------

# Development Workflow

### Backend

``` bash
python -m uvicorn backend.main:app --reload
```

### Frontend

``` bash
cd frontend
npm run dev
```

### Backend tests

``` bash
pytest -q
```

### Frontend production build

``` bash
cd frontend
npm run build
```

------------------------------------------------------------------------

# Current Integration Scope

The integrated version includes:

-   ML-aware live route recommendation
-   P85 risk prediction integration
-   CARF/NLP threat scoring
-   structured route explainability
-   scenario-aware routing
-   physical network visualization
-   route highlighting
-   history storage
-   audit export support
-   deterministic route alerts
-   regression tests covering the integrated modules

The repository is intended to be run locally for demonstration and
development. It is not presented as a production-grade multi-tenant
logistics service.

------------------------------------------------------------------------

## License

See [`LICENSE`](LICENSE).

------------------------------------------------------------------------

## Team

**Supplychainer --- Tathva / TatHack Project**

Built as a collaborative four-member development project.
