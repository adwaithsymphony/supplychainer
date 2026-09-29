import networkx as nx
import math
import time
from typing import List, Dict, Any, Optional
from .multimodal_network import MODE_PROFILES, create_multimodal_network
from .threat_intelligence import ThreatIntelligencePredictor, ContrastiveNLPEngine, CARFFilter
from .news_ingestion import DynamicNewsIngestor
from .node_resolver import NodeResolver
from .explainability import explain_route

class RouteRecommender:
    """
    Supplychainer Unified Multimodal Optimization Engine.
    V8: Virtual-Node Forensic Edition.
    """

    def __init__(self, network, predictor, simulator, scenario_mgr, demo_mode=False):
        self.network = network # Legacy
        self.predictor = predictor
        self.simulator = simulator
        self.scenario_mgr = scenario_mgr
        self.demo_mode = demo_mode
        self.is_warmed_up = False
        self.warmup_failed = False
        
        self.nlp = ContrastiveNLPEngine(lazy_load=True)
        self.carf = CARFFilter()
        self.news_ingestor = DynamicNewsIngestor()
        self.resolver = NodeResolver()
        
        print(f"[STARTUP] Initializing Split-Node Global Topology...")
        self.unified_graph = create_multimodal_network()
        
        if self.demo_mode:
            self.is_warmed_up = True
            
        print(f"[STARTUP] Unified Engine Ready.")

    def run_background_warmup(self):
        if self.is_warmed_up: return
        print("[WARMUP] Calibrating global threat floor...")
        try:
            self.predictor.warmup()
            self.nlp.warmup()

            # warmup() methods may fail closed by leaving their component unready.
            # Do not advertise a fully operational risk engine in that state.
            if not getattr(self.predictor, "is_trained", False):
                raise RuntimeError("p85 predictor artifacts were not loaded")
            if not getattr(self.nlp, "_ready", False):
                raise RuntimeError("contrastive NLP engine is not ready")

            # Enrich unified graph with baseline intelligence
            for u, v, d in self.unified_graph.edges(data=True):
                mode = d.get("transport_mode", "road")
                if mode == "transfer": continue
                news = self.news_ingestor.fallback_news.get(mode, "Normal conditions.")
                score = self.nlp.get_semantic_score(news)
                threat = self.carf.apply_filter(score, news, mode)
                self.unified_graph[u][v]["base_threat"] = threat
                self.unified_graph[u][v]["base_news"] = news
                
            self.is_warmed_up = True
            print("[WARMUP] Unified Calibration Complete.")
        except Exception as e:
            print(f"[WARMUP] Error during warmup: {e}")
            self.warmup_failed = True

    def recommend(self, source: str, destination: str, transport_preference: str = "any", 
                  routing_policy: str = "STRICT", cargo_type: str = "general", 
                  priority: str = "normal", scenario: str = None, 
                  overrides: dict = None) -> dict:
        
        t0 = time.perf_counter()
        overrides = overrides or {}
        avoid_hubs = overrides.get("avoid_chokepoints", [])
        cost_ceiling = overrides.get("cost_ceiling", 999999)
        max_delay = overrides.get("max_delay", 9999)
        
        # 1. Resolve Entry/Exit (Virtual Nodes)
        res_s = self.resolver.resolve_node_to_entry_point(source)
        res_d = self.resolver.resolve_node_to_entry_point(destination)
        
        if "error" in res_s: return {"error": res_s["error"]}
        if "error" in res_d: return {"error": res_d["error"]}
        
        s_vnode, d_vnode = res_s["id"], res_d["id"]
        
        # 2. Scenario lookup. Route requests are independent; do not mutate one shared
        # active-scenario value while processing concurrent FastAPI requests.
        active_scenario = self.scenario_mgr.get_scenario(scenario)
        disruptions = self.scenario_mgr.get_disruptions_for(scenario)

        # Cache ML inference across personas. Dijkstra may inspect the same edge
        # multiple times, and FASTEST/SAFEST/BALANCED share the same risk signal.
        ml_risk_cache = {}

        # 3. Persona Optimization
        candidates = []
        errors = []
        for persona in ["FASTEST", "SAFEST", "BALANCED"]:
            try:
                # Build Persona Graph (Applying STRICT constraints)
                G_p = self.unified_graph.copy()
                
                # Apply Hub Avoidance (Prune all virtual nodes for the hub)
                for hub_id in avoid_hubs:
                    nodes_to_remove = [n for n, d in G_p.nodes(data=True) if d.get("physical_id") == hub_id]
                    G_p.remove_nodes_from(nodes_to_remove)
                
                # Apply Transport Preference
                if transport_preference != "any" and routing_policy == "STRICT":
                    allowed_modes = [transport_preference, "transfer", "road"]
                    edges_to_remove = []
                    for u, v, d in G_p.edges(data=True):
                        if d["transport_mode"] not in allowed_modes:
                            edges_to_remove.append((u, v))
                    G_p.remove_edges_from(edges_to_remove)

                # A *_BLOCK scenario is a physical closure, not a finite delay. Remove every
                # virtual node belonging to the affected physical hub so no persona can route
                # through the blocked corridor or intentionally "wait it out".
                if active_scenario and active_scenario.get("closed"):
                    blocked_physical = set(active_scenario.get("affected_nodes", []))
                    blocked_virtual = [
                        n for n, d in G_p.nodes(data=True)
                        if d.get("physical_id") in blocked_physical
                    ]
                    G_p.remove_nodes_from(blocked_virtual)

                def weight_func(u, v, d):
                    mode = d["transport_mode"]
                    base_t = d["baseline_time"]
                    base_c = d.get("cost", 0)
                    
                    # Intelligence factor is mapped to the physical hub reached by this edge.
                    v_data = G_p.nodes[v]
                    p_id = v_data.get("physical_id")
                    
                    threat = d.get("base_threat", 0.05)
                    delay = 0
                    hit = self._edge_disruption(G_p, u, v, disruptions, s_vnode)
                    if hit:
                        threat = max(threat, hit["threat"])
                        delay += hit["delay"]

                    ml_risk = self._get_ml_edge_risk(
                        G_p, u, v, d, hit, ml_risk_cache
                    )
                    if ml_risk:
                        delay += ml_risk["applied_delay"]

                    return self._persona_weight(persona, base_t, base_c, threat, delay)

                path = nx.dijkstra_path(G_p, s_vnode, d_vnode, weight=weight_func)
                
                # Compose Multimodal Path Details
                legs = []
                total_time, total_cost, max_threat = 0, 0, 0
                trace = {
                    "eta": {"transit": 0, "transfer": 0, "scenario": 0, "ml_risk": 0},
                    "cost": {"transit": 0, "transfer": 0, "scenario": 0},
                    "risk": {"baseline": 0, "scenario": 0, "ml_p85": 0}
                }
                route_ml_predictions = []

                for i in range(len(path)-1):
                    u, v = path[i], path[i+1]
                    d = G_p[u][v]
                    mode = d["transport_mode"]
                    v_data = G_p.nodes[v]
                    p_id = v_data.get("physical_id")
                    
                    base_time = d["baseline_time"]
                    l_time = base_time
                    l_cost = d.get("cost", 0)
                    base_threat = d.get("base_threat", 0.05)
                    l_threat = base_threat
                    l_news = d.get("base_news", "Standard conditions")
                    l_source = "FALLBACK"

                    hit = self._edge_disruption(G_p, u, v, disruptions, s_vnode)
                    if hit:
                        l_time += hit["delay"]
                        l_threat = max(base_threat, hit["threat"])
                        l_news = hit["reason"]
                        l_source = "SCENARIO"
                        # Keep scenario impact in its own audit bucket so ETA is not double-counted.
                        trace["eta"]["scenario"] += hit["delay"]
                        trace["risk"]["scenario"] = max(trace["risk"]["scenario"], hit["threat"])

                    ml_risk = self._get_ml_edge_risk(
                        G_p, u, v, d, hit, ml_risk_cache
                    )
                    if ml_risk:
                        l_time += ml_risk["applied_delay"]
                        trace["eta"]["ml_risk"] += ml_risk["applied_delay"]
                        if ml_risk.get("p85_delay") is not None:
                            trace["risk"]["ml_p85"] = max(
                                trace["risk"]["ml_p85"], ml_risk["p85_delay"]
                            )
                        route_ml_predictions.append({
                            "from": G_p.nodes[u].get("physical_id", u),
                            "to": p_id,
                            "mode": mode.upper(),
                            "p50_delay": ml_risk.get("p50_delay"),
                            "p85_delay": ml_risk.get("p85_delay"),
                            "p95_delay": ml_risk.get("p95_delay"),
                            "prediction_status": ml_risk.get("prediction_status"),
                            "applied_disruption_delay_hours": round(ml_risk["applied_delay"], 2),
                        })

                    if d["type"] == "transfer":
                        trace["eta"]["transfer"] += base_time
                        trace["cost"]["transfer"] += l_cost
                    else:
                        trace["eta"]["transit"] += base_time
                        trace["cost"]["transit"] += l_cost
                        trace["risk"]["baseline"] = max(trace["risk"]["baseline"], base_threat)

                    total_time += l_time
                    total_cost += l_cost
                    max_threat = max(max_threat, l_threat)
                    
                    legs.append({
                        "from": G_p.nodes[u].get("physical_id", u),
                        "to": p_id,
                        "to_name": v_data.get("display_name", p_id),
                        "mode": mode.upper(),
                        "type": d["type"],
                        "eta": round(l_time, 1),
                        "cost": round(l_cost, 2),
                        "threat": round(l_threat, 2),
                        "reason": l_news,
                        "intel_source": l_source
                    })

                if total_cost > cost_ceiling or total_time > (max_delay * 24): continue

                candidates.append({
                    "persona": persona,
                    "primary_mode": "MULTIMODAL",
                    "legs": legs,
                    "adjusted_eta": round(total_time, 1),
                    "total_cost": round(total_cost, 2),
                    "threat_level": round(max_threat, 2),
                    "risk_prediction": self._summarize_route_risk(route_ml_predictions),
                    "audit_trace": trace,
                    "route_explanation": explain_route(
                        persona=persona, legs=legs, eta=round(total_time, 1), cost=round(total_cost, 2),
                        threat=round(max_threat, 2), scenario=active_scenario.get("name") if active_scenario else None,
                        constraints={"routing_policy": routing_policy, "transport_preference": transport_preference,
                                     "cost_ceiling": cost_ceiling, "max_delay_hours": max_delay,
                                     "avoid_chokepoints": list(avoid_hubs)},
                        predicted_delay=(
                            sum(p.get("applied_disruption_delay_hours", 0.0) for p in route_ml_predictions)
                            if route_ml_predictions else None
                        ),
                    ),
                    "explanation": self._generate_forensic_explanation(persona, legs, trace, max_threat, total_time, total_cost),
                    "override_applied": bool(avoid_hubs or cost_ceiling < 999999)
                })

            except nx.NetworkXNoPath:
                continue
            except Exception as e:
                print(f"[ROUTING ERROR] {persona}: {type(e).__name__}: {e}")
                errors.append(f"{persona}: {type(e).__name__}: {e}")

        if not candidates:
            if errors:
                return {
                    "error": "Routing failed with an internal error (not a no-route result).",
                    "details": errors,
                }
            return {"error": "No valid multimodal route established under current strategic constraints."}

        # Deduplicate and sort
        final = []
        seen = set()
        for c in sorted(candidates, key=lambda x: x["adjusted_eta"]):
            path_sig = tuple([l["to"] for l in c["legs"]])
            if path_sig not in seen:
                final.append(c)
                seen.add(path_sig)

        recommendations = final[:3]
        for candidate in recommendations:
            if "route_explanation" in candidate:
                candidate["route_explanation"]["alternatives"] = [
                    {"persona": other.get("persona"), "eta_hours": other.get("adjusted_eta"),
                     "cost": other.get("total_cost"), "threat": other.get("threat_level")}
                    for other in recommendations if other is not candidate
                ]

        return {
            "origin": source, "destination": destination,
            "active_scenario": active_scenario["name"] if active_scenario else None,
            "recommendations": recommendations
        }

    def _get_ml_edge_risk(self, G, u, v, edge, hit, cache):
        """Return the real P85 risk contribution for one affected/meaningfully risky edge.

        The production model predicts operational delay even under clear conditions.
        Normal routing must not be distorted by that systemic floor, so only the
        disruption component above the model's systemic floor is added to routing.
        Prediction failures remain explicit and use the predictor's conservative
        fallback delay rather than silently becoming zero.
        """
        mode = edge.get("transport_mode", "road")
        if mode == "transfer":
            return None

        base_threat = float(edge.get("base_threat", 0.05))
        scenario_threat = float(hit.get("threat", 0.0)) if hit else 0.0
        risk_signal = max(base_threat, scenario_threat)

        # 0.05 is the existing routing threat floor. Below/at that floor there is
        # no meaningful disruption signal to feed into the quantile risk layer.
        if risk_signal <= 0.05:
            return None

        key = (u, v, mode, round(risk_signal, 6), round(float(hit.get("delay", 0.0)), 6) if hit else 0.0)
        if key in cache:
            return cache[key]

        if self.predictor is None:
            fallback_priors = {"road": 2.5, "sea": 48.0, "air": 12.0, "rail": 18.0}
            fallback = fallback_priors.get(mode, 12.0)
            result = {
                "p50_delay": None, "p85_delay": None, "p95_delay": None,
                "prediction_status": "UNAVAILABLE_NO_PREDICTOR",
                "final_delay_presented": fallback,
                "baseline_systemic_friction": fallback,
                "is_defensible": False,
            }
        else:
            origin = self._model_location_name(G.nodes[u])
            destination = self._model_location_name(G.nodes[v])
            result = self.predictor.predict_worst_case_delay(
                origin, destination, mode,
                leg_type="Global_Freight",
                condition_flag="Clear",
                nlp_score=risk_signal,
            )

        p85 = result.get("p85_delay")
        baseline = float(result.get("baseline_systemic_friction") or 0.0)
        status = result.get("prediction_status", "UNKNOWN")

        if p85 is not None:
            # The model's floor represents normal operational friction. Only the
            # disruption increment is allowed to change the route score.
            applied_delay = max(0.0, float(p85) - baseline)
        else:
            # Explicit fallback/uncertainty path: preserve a conservative delay
            # rather than converting a failed inference into optimistic zero.
            presented = result.get("final_delay_presented")
            applied_delay = max(0.0, float(presented)) if presented is not None else 0.0

        risk = {
            "p50_delay": result.get("p50_delay"),
            "p85_delay": p85,
            "p95_delay": result.get("p95_delay"),
            "prediction_status": status,
            "is_defensible": bool(result.get("is_defensible", False)),
            "applied_delay": round(applied_delay, 6),
        }
        cache[key] = risk
        return risk

    @staticmethod
    def _model_location_name(node_data: dict) -> str:
        """Prefer the canonical parent city because the production encoder is city/hub based."""
        return node_data.get("parent_city") or node_data.get("display_name") or node_data.get("physical_id", "Unknown")

    @staticmethod
    def _summarize_route_risk(predictions: list) -> dict:
        """Expose only real quantiles; route-level P85 is explicitly max-leg P85, not a fabricated route quantile."""
        if not predictions:
            return {
                "p50_delay": None,
                "p85_delay": None,
                "p95_delay": None,
                "prediction_status": "NO_MEANINGFUL_DISRUPTION",
                "available_quantiles": [],
                "aggregation": "none",
                "predicted_disruption_delay_hours": 0.0,
                "observations": [],
            }

        p85_values = [p["p85_delay"] for p in predictions if p.get("p85_delay") is not None]
        statuses = {p.get("prediction_status") for p in predictions}
        if all(s == "MODEL_P85" for s in statuses):
            status = "MODEL_P85"
        elif any(s == "FALLBACK_INFERENCE_ERROR" for s in statuses):
            status = "FALLBACK_INFERENCE_ERROR"
        else:
            status = "MIXED"

        return {
            "p50_delay": None,
            "p85_delay": round(max(p85_values), 2) if p85_values else None,
            "p95_delay": None,
            "prediction_status": status,
            "available_quantiles": ["p85"] if p85_values else [],
            "aggregation": "max_leg_p85_not_route_quantile",
            "predicted_disruption_delay_hours": round(sum(p["applied_disruption_delay_hours"] for p in predictions), 2),
            "observations": predictions,
        }

    @staticmethod
    def _persona_weight(persona: str, base_t: float, base_c: float, threat: float, delay: float) -> float:
        """Pure Dijkstra edge weight for a routing persona."""
        if persona == "FASTEST":
            return base_t + delay
        if persona == "SAFEST":
            risk_penalty = 1.0 + (threat * 12.0)
            return (base_t + delay) * risk_penalty

        # BALANCED: express risk as threat-weighted exposure hours rather than a flat constant.
        time_weight = 0.3
        cost_weight = 0.5
        risk_weight = 0.2
        exposed_hours = threat * (base_t + delay)
        return (base_t + delay) * time_weight + (base_c / 150.0) * cost_weight + exposed_hours * risk_weight

    @staticmethod
    def _edge_disruption(G, u, v, disruptions: dict, origin_vnode: str) -> Optional[dict]:
        """Return disruption impact for one physical hub visit, or None."""
        if not disruptions:
            return None
        pu = G.nodes[u].get("physical_id")
        pv = G.nodes[v].get("physical_id")
        hits = []
        if pv != pu and pv in disruptions:
            hits.append(disruptions[pv])
        if u == origin_vnode and pu in disruptions:
            hits.append(disruptions[pu])
        if not hits:
            return None
        return {
            "delay": sum(h["delay"] for h in hits),
            "threat": max(h["threat"] for h in hits),
            "reason": " | ".join(dict.fromkeys(h["reason"] for h in hits)),
        }

    def _generate_forensic_explanation(self, persona, legs, trace, threat, total_time, total_cost):
        """Generate an explanation from actual route numbers, not invented comparisons."""
        transfers = sum(1 for l in legs if l["type"] == "transfer")
        scenario_h = round(trace["eta"]["scenario"], 1)
        tail = f"ETA {round(total_time, 1)}h, cost ${round(total_cost, 2):,.2f}, peak threat {round(threat, 2)}, {transfers} mode transfers"
        if scenario_h > 0:
            tail += f", includes +{scenario_h}h scenario delay"
        if persona == "FASTEST":
            return f"Velocity-optimized: minimizes ETA. {tail}."
        if persona == "SAFEST":
            return f"Resilience-optimized: penalizes threat exposure and avoids high-risk corridors. {tail}."
        return f"Balanced: weighs transit time, cost and threat-weighted exposure. {tail}."
