from fastapi import FastAPI, WebSocket, Query
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import json
import random
import os
from contextlib import asynccontextmanager

from fastapi.middleware.cors import CORSMiddleware
from .engine.graph_model import create_logistics_network
from .engine.simulator import LogisticsSimulator
from .engine.threat_intelligence import ThreatIntelligencePredictor
from .engine.baseline import BaselineRouter
from .engine.weather_integration import APIWeatherProvider
from .engine.multimodal_network import create_multimodal_network, get_city_capabilities, load_canonical_hubs
from .engine.route_recommender import RouteRecommender
from .engine.scenario_manager import ScenarioManager
from .engine.supplier_scorer import SupplierScorer
from .engine.history_store import RouteHistoryStore
from .engine.audit_export import export_csv
from .engine.alert_engine import RouteAlertEngine
from fastapi.responses import Response

# Global Engine State
network = create_logistics_network() # Still US-only simulator
simulator = LogisticsSimulator(network, weather_provider=APIWeatherProvider())
predictor = ThreatIntelligencePredictor() 
baseline = BaselineRouter(network)

# Product layer (Supplychainer Architecture) - Now using Canonical Hubs
multimodal_net = create_multimodal_network()
scenario_mgr = ScenarioManager()
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
recommender = RouteRecommender(multimodal_net, predictor, simulator, scenario_mgr, demo_mode=DEMO_MODE)
canonical_hubs = load_canonical_hubs()
supplier_scorer = SupplierScorer(os.path.join(os.path.dirname(__file__), 'data', 'suppliers.json'))
history_store = RouteHistoryStore()
alert_engine = RouteAlertEngine(multimodal_net, scenario_mgr)


class RecommendRequest(BaseModel):
    source: str # This should be a Canonical Hub ID or City Name
    destination: str # This should be a Canonical Hub ID or City Name
    cargo_type: str = "general"
    priority: str = "normal"
    budget_sensitivity: str = "medium"
    transport_preference: str = "any" # sea, air, rail, road, any
    routing_policy: str = "STRICT" # STRICT or PREFERRED
    scenario: Optional[str] = None
    overrides: Optional[dict] = None

class AlertRequest(BaseModel):
    source: str
    destination: str
    cargo_type: str = "general"
    priority: str = "normal"
    transport_preference: str = "any"
    routing_policy: str = "STRICT"
    scenario: str
    route: Optional[dict] = None


class SourcingRequest(BaseModel):
    category: str = "Electronics"
    current_inventory: int = 1000
    safety_stock: int = 1500
    demand_forecast: int = 800
    scenario: Optional[str] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Supplychainer Engine Active: Canonical Global Registry Loaded.")
    if not DEMO_MODE:
        asyncio.create_task(asyncio.to_thread(recommender.run_background_warmup))
    yield

app = FastAPI(title="Smart Supply Chain API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/scenarios")
def get_scenarios():
    """Returns available disruption scenarios."""
    return scenario_mgr.get_all_scenarios()

@app.get("/api/hubs")
def get_hubs():
    """Returns the full canonical hub registry."""
    return canonical_hubs

@app.get("/api/hubs/search")
def search_hubs(q: str = Query(..., min_length=1)):
    """Search hubs by display_name, aliases, or country."""
    q = q.lower()
    results = []
    for hub in canonical_hubs:
        if (q in hub["display_name"].lower() or 
            any(q in a.lower() for a in hub["aliases"]) or 
            q in hub["country"].lower() or
            q in hub["id"].lower()):
            results.append(hub)
    return results

@app.get("/api/network")
def get_network():
    """Return the physical multimodal topology used by the executive map.

    The routing graph remains split into virtual mode-specific nodes internally.
    This endpoint only projects that graph into physical hubs/corridors for
    visualization; it does not alter routing or scenario behavior.
    """
    nodes_by_id = {}
    for node_id, data in multimodal_net.nodes(data=True):
        physical_id = data.get("physical_id", node_id)
        if physical_id not in nodes_by_id:
            nodes_by_id[physical_id] = {
                "id": physical_id,
                "display_name": data.get("display_name", physical_id),
                "type": data.get("type"),
                "country": data.get("country"),
                "lat": data.get("lat"),
                "lon": data.get("lon"),
                "importance": data.get("importance", 5),
                "modes": [],
            }
        mode = data.get("mode")
        if mode and mode not in nodes_by_id[physical_id]["modes"]:
            nodes_by_id[physical_id]["modes"].append(mode)

    edges = []
    seen = set()
    for u, v, data in multimodal_net.edges(data=True):
        source = multimodal_net.nodes[u].get("physical_id", u)
        target = multimodal_net.nodes[v].get("physical_id", v)
        mode = data.get("transport_mode", "unknown")
        edge_type = data.get("type", "transit")

        edge_key = (source, target, mode, edge_type)
        reverse_key = (target, source, mode, edge_type)
        if edge_key in seen or reverse_key in seen:
            continue

        edges.append({
            "source": source,
            "target": target,
            "mode": mode,
            "type": edge_type,
            "baseline_time": data.get("baseline_time"),
            "distance": data.get("distance"),
        })
        seen.add(edge_key)

    return {"nodes": list(nodes_by_id.values()), "edges": edges}

@app.get("/api/status")
def get_status():
    return {
        "ml_trained": True,
        "active_trips": len(simulator.active_trips),
        "tick": simulator.time_tick,
        "is_supplychainer": True,
        "geo_scope": "Global (Canonical)",
        "hub_count": len(canonical_hubs)
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            if recommender.warmup_failed:
                status_msg = "WARM-UP FAILED"
            elif not recommender.is_warmed_up:
                status_msg = "WARMING RISK ENGINE"
            else:
                status_msg = "FULLY OPERATIONAL"
                
            state = {
                "tick": simulator.time_tick,
                "ml_trained": True,
                "engine_status": status_msg,
                "hub_registry": "Synchronized"
            }
            await websocket.send_text(json.dumps(state))
            await asyncio.sleep(2.0)
    except Exception as e:
        print(f"WebSocket closed: {e}")

@app.get("/api/cities")
def get_cities():
    """Returns the city-to-hub mapping for multimodal resolution."""
    path = os.path.join(os.path.dirname(__file__), 'data', 'canonical_locations.json')
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {}

@app.post("/api/recommend")
def recommend_routes(req: RecommendRequest):
    result = recommender.recommend(
        source=req.source,
        destination=req.destination,
        cargo_type=req.cargo_type,
        priority=req.priority,
        transport_preference=req.transport_preference,
        routing_policy=req.routing_policy,
        scenario=req.scenario,
        overrides=req.overrides
    )
    if result.get("recommendations"):
        request_data = req.model_dump()
        for recommendation in result["recommendations"]:
            history_store.save_recommendation(
                request_data,
                recommendation,
                scenario_name=result.get("active_scenario"),
            )
    return result

@app.post("/api/suppliers")
def get_suppliers(req: SourcingRequest):
    # Get active disruptions from scenario manager
    active_disruptions = {}
    if req.scenario:
        scenario_mgr.activate_scenario(req.scenario)
        active_disruptions = scenario_mgr.get_active_disruptions()
    
    ranked_suppliers = supplier_scorer.get_ranked_suppliers(req.category, active_disruptions)
    advice = supplier_scorer.get_procurement_advice(req.current_inventory, req.safety_stock, req.demand_forecast)
    
    return {
        "suppliers": ranked_suppliers,
        "advice": advice,
        "active_disruptions": active_disruptions
    }


@app.get("/api/history")
def get_history(limit: int = Query(100, ge=1, le=1000)):
    """Return persisted route decisions, newest first."""
    return {"history": history_store.list_records(limit)}


@app.get("/api/history/export")
def export_history_csv(limit: int = Query(1000, ge=1, le=1000)):
    """Export persisted route decisions as an audit-ready CSV."""
    csv_data = export_csv(history_store.list_records(limit))
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="route_audit.csv"'},
    )


@app.post("/api/alerts")
def get_route_alert(req: AlertRequest):
    """Evaluate a current route against a deterministic disruption scenario."""
    route = req.route
    if route is None:
        baseline = recommender.recommend(
            source=req.source,
            destination=req.destination,
            cargo_type=req.cargo_type,
            priority=req.priority,
            transport_preference=req.transport_preference,
            routing_policy=req.routing_policy,
            scenario=None,
        )
        if not baseline.get("recommendations"):
            return {
                "severity": "info",
                "event": None,
                "route_affected": False,
                "impact": "No current route is available to evaluate.",
                "recommended_action": "No route change required",
            }
        route = baseline["recommendations"][0]
    return alert_engine.evaluate(route, req.scenario)
