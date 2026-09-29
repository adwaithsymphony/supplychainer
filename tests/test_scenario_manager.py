from backend.engine.scenario_manager import ScenarioManager


def test_suez_block_is_marked_as_physical_closure():
    mgr = ScenarioManager()
    scenario = mgr.get_scenario("SUEZ_BLOCK")
    assert scenario["closed"] is True
    assert scenario["affected_nodes"] == ["CHOKE-SUEZ"]


def test_scenario_lookup_is_request_local():
    mgr = ScenarioManager()
    first = mgr.get_disruptions_for("SUEZ_BLOCK")
    second = mgr.get_disruptions_for("LA_PORT_STRIKE")
    assert "CHOKE-SUEZ" in first
    assert "PORT-LOSANGELES" in second
    assert "CHOKE-SUEZ" not in second
