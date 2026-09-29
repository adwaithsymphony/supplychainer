import csv
import io
from fastapi.testclient import TestClient

from backend.engine.alert_engine import RouteAlertEngine
from backend.engine.history_store import RouteHistoryStore
from backend.engine.multimodal_network import create_multimodal_network
from backend.engine.scenario_manager import ScenarioManager


def test_route_is_saved_and_history_retrieved(tmp_path, monkeypatch):
    import backend.main as main
    store = RouteHistoryStore(str(tmp_path / "history.sqlite3"))
    monkeypatch.setattr(main, "history_store", store)

    with TestClient(main.app) as client:
        response = client.post("/api/recommend", json={
            "source": "Shanghai",
            "destination": "Rotterdam",
            "cargo_type": "general",
            "priority": "normal",
            "transport_preference": "any",
            "routing_policy": "STRICT",
            "scenario": "SUEZ_BLOCK",
        })
        assert response.status_code == 200
        history = client.get("/api/history")
        assert history.status_code == 200
        records = history.json()["history"]
        assert records
        record = records[0]
        assert record["source"] == "Shanghai"
        assert record["destination"] == "Rotterdam"
        assert record["scenario"] == "SUEZ_BLOCK"
        assert record["selected_route"]["legs"]
        assert record["eta"] >= 0
        assert record["cost"] >= 0
        assert "audit_information" in record


def test_csv_export_works(tmp_path, monkeypatch):
    import backend.main as main
    store = RouteHistoryStore(str(tmp_path / "history.sqlite3"))
    monkeypatch.setattr(main, "history_store", store)

    store.save_recommendation(
        {
            "source": "Shanghai", "destination": "Rotterdam",
            "cargo_type": "general", "priority": "normal",
            "transport_preference": "sea", "scenario": "SUEZ_BLOCK",
        },
        {
            "persona": "FASTEST",
            "legs": [{"from": "PORT-SHA", "to": "CHOKE-SUEZ"}],
            "adjusted_eta": 100,
            "total_cost": 2000,
            "threat_level": 1.0,
            "explanation": "Recorded decision",
        },
    )

    with TestClient(main.app) as client:
        response = client.get("/api/history/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows[0]["route"] == "PORT-SHA → CHOKE-SUEZ"
    assert rows[0]["scenario"] == "SUEZ_BLOCK"
    assert rows[0]["decision"] == "Recorded decision"


def _route_with_nodes(*nodes):
    return {"legs": [{"from": a, "to": b} for a, b in zip(nodes, nodes[1:])]}


def test_affected_route_creates_alert():
    engine = RouteAlertEngine(create_multimodal_network(), ScenarioManager())
    route = _route_with_nodes("PORT-SHANGHAI", "CHOKE-SUEZ", "PORT-ROTTERDAM")
    alert = engine.evaluate(route, "SUEZ_BLOCK")
    assert alert["route_affected"] is True
    assert alert["severity"] == "critical"
    assert alert["event"] == "Suez Canal Blockage"
    assert alert["recommended_action"] == "Recalculate route"


def test_unaffected_route_does_not_create_false_alert():
    engine = RouteAlertEngine(create_multimodal_network(), ScenarioManager())
    route = _route_with_nodes("PORT-LOSANGELES", "PORT-LONG BEACH")
    alert = engine.evaluate(route, "SUEZ_BLOCK")
    assert alert["route_affected"] is False
    assert alert["severity"] == "info"
    assert alert["recommended_action"] == "No route change required"


def test_suez_block_alert_uses_scenario_data_not_event_name():
    engine = RouteAlertEngine(create_multimodal_network(), ScenarioManager())
    route = _route_with_nodes("PORT-SHANGHAI", "CHOKE-SUEZ")
    alert = engine.evaluate(route, "SUEZ_BLOCK")
    assert "CHOKE-SUEZ" in alert["impact"]
    assert "salvage" in alert["impact"].lower()


def test_alert_api_uses_supplied_current_route():
    import backend.main as main

    with TestClient(main.app) as client:
        response = client.post("/api/alerts", json={
            "source": "Shanghai",
            "destination": "Rotterdam",
            "scenario": "SUEZ_BLOCK",
            "route": _route_with_nodes("PORT-SHANGHAI", "CHOKE-SUEZ", "PORT-ROTTERDAM"),
        })
    assert response.status_code == 200
    body = response.json()
    assert body["route_affected"] is True
    assert body["recommended_action"] == "Recalculate route"
