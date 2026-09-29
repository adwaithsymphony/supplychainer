import networkx as nx

from backend.engine.route_recommender import RouteRecommender
from backend.engine.scenario_manager import ScenarioManager
from backend.engine.threat_intelligence import ThreatIntelligencePredictor


class StubPredictor:
    def __init__(self, p85_delay=20.0, failure=False):
        self.p85_delay = p85_delay
        self.failure = failure
        self.calls = []

    def predict_worst_case_delay(self, origin, destination, transport_mode, **kwargs):
        self.calls.append({
            "origin": origin,
            "destination": destination,
            "transport_mode": transport_mode,
            **kwargs,
        })
        if self.failure:
            return {
                "p50_delay": None,
                "p85_delay": None,
                "p95_delay": None,
                "prediction_status": "FALLBACK_INFERENCE_ERROR",
                "final_delay_presented": 7.0,
                "baseline_systemic_friction": 0.0,
                "is_defensible": False,
            }
        return {
            "p50_delay": None,
            "p85_delay": self.p85_delay,
            "p95_delay": None,
            "prediction_status": "MODEL_P85",
            "final_delay_presented": self.p85_delay,
            "baseline_systemic_friction": 0.0,
            "is_defensible": True,
        }


def make_small_recommender(predictor):
    rec = RouteRecommender(
        network=None,
        predictor=predictor,
        simulator=None,
        scenario_mgr=ScenarioManager(),
        demo_mode=True,
    )

    # Replace the production graph with a deterministic two-route fixture.
    graph = nx.DiGraph()
    for node, city in [("A:road", "A"), ("B:road", "B"), ("C:road", "C"), ("D:road", "D")]:
        graph.add_node(node, physical_id=city, display_name=city, parent_city=city)

    graph.add_edge("A:road", "B:road", baseline_time=5.0, cost=10.0,
                   transport_mode="road", type="transit", base_threat=0.20)
    graph.add_edge("B:road", "D:road", baseline_time=5.0, cost=10.0,
                   transport_mode="road", type="transit", base_threat=0.20)
    graph.add_edge("A:road", "C:road", baseline_time=6.0, cost=10.0,
                   transport_mode="road", type="transit", base_threat=0.05)
    graph.add_edge("C:road", "D:road", baseline_time=6.0, cost=10.0,
                   transport_mode="road", type="transit", base_threat=0.05)
    rec.unified_graph = graph
    rec.resolver.resolve_node_to_entry_point = lambda value: {"id": f"{value}:road"}
    return rec


def route_contains(result, physical_id):
    return any(leg["to"] == physical_id for c in result["recommendations"] for leg in c["legs"])


def test_ml_predictor_is_invoked_by_live_routing():
    predictor = StubPredictor(p85_delay=20.0)
    rec = make_small_recommender(predictor)

    result = rec.recommend("A", "D", transport_preference="road", routing_policy="STRICT")

    assert "error" not in result
    assert predictor.calls, "live routing never invoked the quantile predictor"
    assert all(call["nlp_score"] == 0.2 for call in predictor.calls)


def test_predicted_disruption_delay_changes_route_scoring():
    low = StubPredictor(p85_delay=1.0)
    high = StubPredictor(p85_delay=20.0)

    low_result = make_small_recommender(low).recommend(
        "A", "D", transport_preference="road", routing_policy="STRICT"
    )
    high_result = make_small_recommender(high).recommend(
        "A", "D", transport_preference="road", routing_policy="STRICT"
    )

    assert route_contains(low_result, "B")
    assert route_contains(high_result, "C")


def test_higher_predicted_disruption_makes_affected_route_less_attractive():
    predictor = StubPredictor(p85_delay=20.0)
    rec = make_small_recommender(predictor)
    result = rec.recommend(
        "A", "D", transport_preference="road", routing_policy="STRICT"
    )

    fastest = next(c for c in result["recommendations"] if c["persona"] == "FASTEST")
    assert all(leg["to"] != "B" for leg in fastest["legs"])

    # Inspect the exact affected edge risk that Dijkstra used. The selected route
    # does not contain B anymore, so its route-level payload correctly omits it.
    edge = rec.unified_graph["A:road"]["B:road"]
    risk = rec._get_ml_edge_risk(
        rec.unified_graph, "A:road", "B:road", edge, None, {}
    )
    assert risk["p85_delay"] == 20.0
    assert risk["p50_delay"] is None
    assert risk["p95_delay"] is None


def test_predictor_failure_is_explicit_and_nonzero():
    predictor = StubPredictor(failure=True)
    rec = make_small_recommender(predictor)
    result = rec.recommend("A", "D", transport_preference="road", routing_policy="STRICT")

    assert "error" not in result
    edge = rec.unified_graph["A:road"]["B:road"]
    risk = rec._get_ml_edge_risk(
        rec.unified_graph, "A:road", "B:road", edge, None, {}
    )
    assert risk["prediction_status"] == "FALLBACK_INFERENCE_ERROR"
    assert risk["applied_delay"] > 0
    assert risk["p85_delay"] is None


def test_normal_routing_does_not_apply_ml_when_threat_is_at_existing_floor():
    predictor = StubPredictor(p85_delay=100.0)
    rec = make_small_recommender(predictor)
    result = rec.recommend("A", "D", transport_preference="road", routing_policy="STRICT")

    # The alternative C path is normal (0.05 threat, the existing floor), so the
    # quantile model must not inject systemic delay into otherwise normal routing.
    assert predictor.calls
    # B is the meaningful-risk path, while C remains untouched by ML.
    c_observations = [
        obs for c in result["recommendations"]
        for obs in c["risk_prediction"]["observations"]
        if obs["to"] == "C"
    ]
    assert not c_observations


def test_production_artifact_exposes_only_real_p85_quantile():
    predictor = ThreatIntelligencePredictor(lazy_load=True)
    predictor.warmup()
    result = predictor.predict_worst_case_delay("Seattle", "Shanghai", "sea", nlp_score=0.9)

    assert result["prediction_status"] == "MODEL_P85"
    assert result["p50_delay"] is None
    assert result["p85_delay"] == result["final_delay_presented"]
    assert result["p95_delay"] is None
    assert result["available_quantiles"] == ["p85"]
