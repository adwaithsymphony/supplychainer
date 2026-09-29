import csv
import io
import json
from typing import Any, Dict, Iterable


AUDIT_FIELDS = [
    "route",
    "timestamp",
    "source",
    "destination",
    "cargo",
    "priority",
    "transport_preference",
    "scenario",
    "eta",
    "cost",
    "threat",
    "decision",
    "risk_prediction",
]


def _route_label(record: Dict[str, Any]) -> str:
    route = record.get("selected_route") or {}
    legs = route.get("legs") or []
    if not legs:
        return f"{record.get('source', '')} → {record.get('destination', '')}"
    points = [legs[0].get("from", record.get("source", ""))]
    points.extend(leg.get("to", "") for leg in legs)
    return " → ".join(str(p) for p in points if p)


def export_csv(records: Iterable[Dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=AUDIT_FIELDS)
    writer.writeheader()
    for record in records:
        writer.writerow({
            "route": _route_label(record),
            "timestamp": record.get("timestamp", ""),
            "source": record.get("source", ""),
            "destination": record.get("destination", ""),
            "cargo": record.get("cargo", ""),
            "priority": record.get("priority", ""),
            "transport_preference": record.get("transport_preference", ""),
            "scenario": record.get("scenario") or "",
            "eta": record.get("eta", ""),
            "cost": record.get("cost", ""),
            "threat": record.get("threat", ""),
            "decision": record.get("decision") or record.get("explanation") or "",
            "risk_prediction": json.dumps(record.get("risk_prediction"), sort_keys=True)
            if record.get("risk_prediction") is not None else "",
        })
    return output.getvalue()
