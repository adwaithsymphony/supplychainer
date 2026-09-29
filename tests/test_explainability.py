from backend.engine.explainability import explain_route, explain_threat


def test_threat_explanation_is_structured_and_does_not_invent_margin():
    item = explain_threat(event_text="Port strike", transport_mode="SEA", semantic_score=.8,
                          threat_score=.8, carf_score=.8, affected_location="Port X")
    assert item["affected_mode"] == "sea"
    assert item["semantic_margin"] is None
    assert item["carf"]["decision"] == "RETAINED"
    assert item["threat_score"] == item["carf"]["score"]


def test_route_explanation_uses_actual_metrics_and_scenario_reason():
    legs = [{"from": "A", "to": "B", "mode": "SEA", "intel_source": "SCENARIO",
             "reason": "Corridor closure", "eta": 12.0, "threat": .9}]
    out = explain_route(persona="FASTEST", legs=legs, eta=12, cost=300, threat=.9, scenario="TEST_BLOCK")
    assert out["metrics"] == {"eta_hours": 12.0, "cost": 300.0, "threat": .9, "predicted_delay_hours": None}
    assert "Corridor closure" in out["selection_basis"][1]
    assert out["affected_legs"][0]["to"] == "B"


def test_route_explanation_mentions_active_closure_scenario_without_hardcoding_name():
    out = explain_route(persona="BALANCED", legs=[], eta=40, cost=900, threat=.1, scenario="SUEZ_BLOCK")
    assert "SUEZ_BLOCK" in out["selection_basis"][1]
