from backend.engine.multimodal_network import create_multimodal_network
from backend.engine.route_recommender import RouteRecommender
from backend.engine.scenario_manager import ScenarioManager


def make_recommender():
    graph = create_multimodal_network()
    return RouteRecommender(graph, None, None, ScenarioManager(), demo_mode=True)


def _contains_suez(candidate):
    return any(leg["to"] == "CHOKE-SUEZ" for leg in candidate["legs"])


def test_normal_balanced_route_can_use_suez():
    rec = make_recommender()
    result = rec.recommend("Shanghai", "Rotterdam", transport_preference="any", routing_policy="STRICT")
    assert "error" not in result
    assert any(_contains_suez(c) for c in result["recommendations"])


def test_suez_block_avoids_suez_for_every_persona_in_any_mode():
    rec = make_recommender()
    result = rec.recommend("Shanghai", "Rotterdam", transport_preference="any", routing_policy="STRICT", scenario="SUEZ_BLOCK")
    assert "error" not in result
    assert result["recommendations"]
    assert all(not _contains_suez(c) for c in result["recommendations"])


def test_suez_block_avoids_suez_for_sea_fastest_and_safest():
    rec = make_recommender()
    result = rec.recommend("Shanghai", "Rotterdam", transport_preference="sea", routing_policy="STRICT", scenario="SUEZ_BLOCK")
    assert "error" not in result
    assert result["recommendations"]
    assert all(not _contains_suez(c) for c in result["recommendations"])


def test_suez_block_removes_physical_suez_nodes_from_graph():
    rec = make_recommender()
    scenario = rec.scenario_mgr.get_scenario("SUEZ_BLOCK")
    graph = rec.unified_graph.copy()
    blocked = {n for n, d in graph.nodes(data=True) if d.get("physical_id") in scenario["affected_nodes"]}
    assert blocked
    assert all(graph.nodes[n]["physical_id"] == "CHOKE-SUEZ" for n in blocked)


def test_scenario_trace_does_not_double_count_delay_or_cost():
    rec = make_recommender()
    result = rec.recommend("Shanghai", "Rotterdam", transport_preference="sea", routing_policy="STRICT", scenario="LA_PORT_STRIKE")
    assert "error" not in result
    for candidate in result["recommendations"]:
        legs = candidate["legs"]
        trace = candidate["audit_trace"]
        leg_eta = round(sum(l["eta"] for l in legs), 1)
        leg_cost = round(sum(l["cost"] for l in legs), 2)
        trace_eta = round(sum(trace["eta"].values()), 1)
        trace_cost = round(sum(trace["cost"].values()), 2)
        assert candidate["adjusted_eta"] == leg_eta
        assert abs(candidate["total_cost"] - leg_cost) <= 0.011
        assert trace_eta == candidate["adjusted_eta"]
        assert abs(trace_cost - candidate["total_cost"]) <= 0.011


def test_baseline_risk_does_not_include_scenario_threat():
    rec = make_recommender()
    result = rec.recommend("Shanghai", "Rotterdam", transport_preference="sea", routing_policy="STRICT", scenario="SUEZ_BLOCK")
    assert "error" not in result
    for candidate in result["recommendations"]:
        assert candidate["audit_trace"]["risk"]["scenario"] == 0.0
        assert candidate["threat_level"] <= 0.05
