from fastapi.testclient import TestClient


def test_recommend_api_enforces_suez_block():
    from backend.main import app

    with TestClient(app) as client:
        response = client.post("/api/recommend", json={
            "source": "Shanghai",
            "destination": "Rotterdam",
            "cargo_type": "general",
            "priority": "normal",
            "transport_preference": "sea",
            "routing_policy": "STRICT",
            "scenario": "SUEZ_BLOCK",
        })
    assert response.status_code == 200
    body = response.json()
    assert "error" not in body
    assert all(
        leg["to"] != "CHOKE-SUEZ"
        for candidate in body["recommendations"]
        for leg in candidate["legs"]
    )
