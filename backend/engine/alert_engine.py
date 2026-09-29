from typing import Any, Dict, Optional, Set


class RouteAlertEngine:
    """Deterministic scenario alerting based on route/network/scenario data."""

    def __init__(self, network, scenario_manager):
        self.network = network
        self.scenario_manager = scenario_manager

    def _known_physical_ids(self) -> Set[str]:
        return {
            data.get("physical_id")
            for _, data in self.network.nodes(data=True)
            if data.get("physical_id")
        }

    def _route_physical_ids(self, route: Dict[str, Any]) -> Set[str]:
        route_ids: Set[str] = set()
        legs = route.get("legs") or []
        for leg in legs:
            for key in ("from", "to"):
                value = leg.get(key)
                if value:
                    route_ids.add(str(value))
        return route_ids

    def evaluate(self, route: Dict[str, Any], scenario_id: Optional[str]) -> Dict[str, Any]:
        scenario = self.scenario_manager.get_scenario(scenario_id)
        if not scenario:
            return {
                "severity": "info",
                "event": None,
                "route_affected": False,
                "impact": "No disruption scenario is active.",
                "recommended_action": "No route change required",
            }

        known_nodes = self._known_physical_ids()
        route_nodes = self._route_physical_ids(route)
        affected_nodes = set(scenario.get("affected_nodes", []))

        # A scenario can only affect a route when both the route and scenario
        # refer to physical nodes that actually exist in the current network.
        affected = (
            bool(route_nodes)
            and bool(affected_nodes & known_nodes)
            and bool(route_nodes & affected_nodes & known_nodes)
        )

        threat = float(scenario.get("threat_level", 0))
        if threat >= 0.9:
            severity = "critical"
        elif threat >= 0.7:
            severity = "high"
        elif threat >= 0.4:
            severity = "medium"
        else:
            severity = "low"

        if affected:
            impacted = sorted(route_nodes & affected_nodes & known_nodes)
            impact = (
                f"Current route passes through affected network node(s): "
                f"{', '.join(impacted)}. {scenario.get('reason', '')}"
            ).strip()
            action = "Recalculate route"
        else:
            impact = (
                f"Scenario affects {', '.join(sorted(affected_nodes & known_nodes)) or 'no known network nodes'}; "
                "the current route does not traverse those nodes."
            )
            action = "No route change required"

        return {
            "severity": severity if affected else "info",
            "event": scenario.get("name"),
            "route_affected": affected,
            "impact": impact,
            "recommended_action": action,
        }
