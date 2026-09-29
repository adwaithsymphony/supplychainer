import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RouteHistoryStore:
    """Small SQLite-backed store for auditable route decisions."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv(
            "SUPPLYCHAINER_HISTORY_DB",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "route_history.sqlite3"),
        )
        self._lock = threading.Lock()
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _initialize(self):
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS route_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    cargo TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    transport_preference TEXT NOT NULL,
                    scenario TEXT,
                    selected_route TEXT NOT NULL,
                    eta REAL NOT NULL,
                    cost REAL NOT NULL,
                    threat REAL NOT NULL,
                    risk_prediction TEXT,
                    explanation TEXT,
                    decision TEXT NOT NULL,
                    audit_information TEXT
                )
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(route_history)")}
            if "audit_information" not in columns:
                conn.execute("ALTER TABLE route_history ADD COLUMN audit_information TEXT")
            conn.commit()

    def save_recommendation(
        self,
        request: Dict[str, Any],
        recommendation: Dict[str, Any],
        *,
        scenario_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        timestamp = utc_timestamp()
        route = {
            "persona": recommendation.get("persona"),
            "primary_mode": recommendation.get("primary_mode"),
            "legs": recommendation.get("legs", []),
        }
        risk_prediction = recommendation.get("risk_prediction")
        if risk_prediction is None:
            trace = recommendation.get("audit_trace") or {}
            risk_prediction = trace.get("prediction")

        decision = recommendation.get("explanation") or ""
        audit_information = recommendation.get("audit_trace")
        record = {
            "timestamp": timestamp,
            "source": request.get("source"),
            "destination": request.get("destination"),
            "cargo": request.get("cargo_type", "general"),
            "priority": request.get("priority", "normal"),
            "transport_preference": request.get("transport_preference", "any"),
            "scenario": request.get("scenario") or scenario_name,
            "selected_route": route,
            "eta": float(recommendation.get("adjusted_eta", 0)),
            "cost": float(recommendation.get("total_cost", 0)),
            "threat": float(recommendation.get("threat_level", 0)),
            "risk_prediction": risk_prediction,
            "explanation": decision,
            "decision": decision,
            "audit_information": audit_information,
        }
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO route_history (
                    timestamp, source, destination, cargo, priority,
                    transport_preference, scenario, selected_route,
                    eta, cost, threat, risk_prediction, explanation, decision, audit_information
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["timestamp"], record["source"], record["destination"],
                    record["cargo"], record["priority"], record["transport_preference"],
                    record["scenario"], json.dumps(record["selected_route"], sort_keys=True),
                    record["eta"], record["cost"], record["threat"],
                    json.dumps(record["risk_prediction"], sort_keys=True)
                    if record["risk_prediction"] is not None else None,
                    record["explanation"], record["decision"],
                    json.dumps(record["audit_information"], sort_keys=True)
                    if record["audit_information"] is not None else None,
                ),
            )
            record["id"] = cur.lastrowid
            conn.commit()
        return record

    def list_records(self, limit: int = 100) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._lock, self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM route_history ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()

        records = []
        for row in rows:
            item = dict(row)
            item["selected_route"] = json.loads(item["selected_route"])
            item["risk_prediction"] = (
                json.loads(item["risk_prediction"])
                if item["risk_prediction"] else None
            )
            item["audit_information"] = (
                json.loads(item["audit_information"])
                if item["audit_information"] else None
            )
            records.append(item)
        return records
