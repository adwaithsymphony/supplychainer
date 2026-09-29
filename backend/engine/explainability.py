"""Structured, data-grounded explanations for threat and route decisions."""
from typing import Any, Dict, Optional, Sequence


def explain_threat(*, event_text: str, transport_mode: str, semantic_score: Optional[float],
                   threat_score: float, carf_score: float, affected_location: Optional[str] = None,
                   semantic_margin: Optional[float] = None) -> Dict[str, Any]:
    """Return auditable evidence without inventing missing model outputs."""
    accepted = float(carf_score) > 0
    reason = (
        "CARF retained the semantic signal for this transport mode."
        if accepted else
        "CARF rejected or zeroed the semantic signal for this transport mode."
    )
    return {
        "event_text": event_text,
        "affected_mode": transport_mode.lower(),
        "affected_location": affected_location,
        "semantic_score": semantic_score,
        "semantic_margin": semantic_margin,
        "carf": {"decision": "RETAINED" if accepted else "REJECTED", "score": float(carf_score)},
        "threat_score": float(threat_score),
        "reason": reason,
    }


def explain_route(*, persona: str, legs: Sequence[Dict[str, Any]], eta: float, cost: float,
                  threat: float, scenario: Optional[str] = None,
                  constraints: Optional[Dict[str, Any]] = None,
                  alternatives: Optional[Sequence[Dict[str, Any]]] = None,
                  predicted_delay: Optional[float] = None) -> Dict[str, Any]:
    """Explain a candidate using route metrics and observed scenario effects."""
    scenario_legs = [leg for leg in legs if leg.get("intel_source") == "SCENARIO"]
    reasons = list(dict.fromkeys(
        str(leg.get("reason")) for leg in scenario_legs
        if leg.get("reason") and leg.get("reason") != "Standard conditions"
    ))
    if scenario_legs:
        basis = "The route includes scenario-affected legs: " + "; ".join(reasons)
    elif scenario:
        basis = f"Scenario {scenario} is active, but no scenario-affected leg is recorded on this candidate route."
    else:
        basis = "No scenario-affected leg is recorded on this candidate route."
    objective = {
        "FASTEST": "Route persona: prioritizes travel time.",
        "SAFEST": "Route persona: penalizes threat exposure.",
        "BALANCED": "Route persona: combines travel time, cost, and threat-weighted exposure.",
    }.get(persona, f"Route persona: {persona}.")
    return {
        "persona": persona,
        "selection_basis": [objective, basis],
        "metrics": {"eta_hours": float(eta), "cost": float(cost), "threat": float(threat),
                    "predicted_delay_hours": predicted_delay},
        "scenario": scenario,
        "constraints": constraints or {},
        "affected_legs": [{"from": leg.get("from"), "to": leg.get("to"),
                           "mode": leg.get("mode"), "reason": leg.get("reason"),
                           "eta_hours": leg.get("eta"), "threat": leg.get("threat")}
                          for leg in scenario_legs],
        "alternatives": list(alternatives or []),
    }
