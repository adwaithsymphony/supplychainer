import numpy as np
import joblib
import os
import torch
import json
import time
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd

# Load Production Artifacts
MODEL_PATH = "./Execution/risk_model.pkl"
ENCODER_PATH = "./Execution/label_encoders.pkl"
NLP_ANCHORS_PATH = "./Execution/nlp_anchors.pt"
CALIBRATION_PATH = "./Execution/calibration_profiles.json"

class ThreatIntelligencePredictor:
    """
    Supplychainer Quantile ML Decision Brain.
    V3: Statistically Defensible Calibration & Geographic Hub Intelligence.
    """
    def __init__(self, lazy_load=False):
        self.is_trained = False
        self.model = None
        self.encoders = None
        self.profiles = {}
        self.available_quantiles = {"p85": 0.85}
        
        # These aliases are derived from the categories present in the production
        # encoder. They are feature-resolution aliases, not synthetic model values.
        self.hub_map = {
            "Seattle": "Seattle Port", "Portland": "Portland Terminal", "San Francisco": "San Francisco Port",
            "Los Angeles": "Los Angeles Port", "Salt Lake City": "Salt Lake City Hub", "Denver": "Denver Terminal",
            "Phoenix": "Phoenix Logistics", "Dallas": "Dallas Corridor", "Houston": "Houston Port",
            "Chicago": "Chicago Rail Hub", "St. Louis": "St. Louis Hub", "Atlanta": "Atlanta Air Hub",
            "Miami": "Miami Port", "New York": "New York Port", "Boston": "Boston Terminal",
            "Mumbai": "Mumbai Port", "Kochi": "Kochi Port", "Delhi": "Delhi Air Cargo", "Chennai": "Chennai Port",
            "Shanghai": "Shanghai Port", "Rotterdam": "Rotterdam Port", "Singapore": "Singapore Port",
            "Dubai": "Dubai Logistics Hub", "Suez Canal": "Suez Canal"
        }
        
        if not lazy_load:
            self.warmup()

    def warmup(self):
        if self.is_trained: return
        print("[PREDICTOR] Starting warmup...")
        if not os.path.exists(MODEL_PATH) or not os.path.exists(ENCODER_PATH):
            print(f"CRITICAL: Production models missing. Running in deterministic fallback mode.")
            return
            
        # 1. Load ML Core
        self.model = joblib.load(MODEL_PATH)
        self.encoders = joblib.load(ENCODER_PATH)
        self.is_trained = True
        
        # 2. Load Statistically Defensible Calibration Profiles
        if os.path.exists(CALIBRATION_PATH):
            with open(CALIBRATION_PATH, 'r') as f:
                self.profiles = json.load(f)
            print(f"Calibration Layer: Loaded {len(self.profiles)} mode profiles from historical p5/p95 analysis.")
        else:
            print("WARNING: Calibration profiles missing. Using defensive fallbacks.")
            self.profiles = {}

        print(f"Supplychainer V3 Brain Loaded: Production-Ready.")

    def _encode_feature(self, value: str, key: str) -> int:
        encoder = self.encoders[key]
        classes = list(encoder.classes_)
        if key in ["Origin_Node", "Destination_Node"]:
            resolved = self.hub_map.get(value, value)
            if resolved in classes: return encoder.transform([resolved])[0]
        if value in classes: return encoder.transform([value])[0]
        if key in ["Origin_Node", "Destination_Node"]:
            # Never silently turn an unseen live-routing location into an arbitrary
            # training category. That would produce a prediction that looks real but
            # is not grounded in the artifact's feature domain. The caller will use
            # the explicit conservative fallback path instead.
            raise ValueError(f"Unsupported {key} feature category: {value!r}")
        # Preserve the repository's established encoder fallback for legacy API
        # inputs such as Condition_Flag="Disrupted".
        return encoder.transform([classes[0]])[0]

    def predict_worst_case_delay(self, origin: str, destination: str, transport_mode: str, 
                                 leg_type: str = "Global_Freight", condition_flag: str = "Clear", 
                                 nlp_score: float = 0.0) -> Dict[str, Any]:
        """
        Stage 4: p85 Quantile Prediction with Statistically Defensible Calibration.
        """
        if not self.is_trained:
            mode_key = transport_mode.lower()
            priors = {"road": 2.5, "sea": 48.0, "air": 12.0, "rail": 18.0}
            delay = priors.get(mode_key, 12.0)
            return {
                "raw_model_prediction": delay,
                "calibrated_delay": delay,
                "baseline_systemic_friction": delay,
                "final_delay_presented": delay,
                "calibration_reason": "Deterministic Operational Prior (Engine Warming)",
                "p_quantile": 0.85,
                "available_quantiles": ["p85"],
                "p50_delay": None,
                "p85_delay": None,
                "p95_delay": None,
                "prediction_status": "FALLBACK_WARMUP",
                "is_defensible": True
            }

        # t_ml_start = time.perf_counter()
        try:
            feat_origin = self._encode_feature(origin, 'Origin_Node')
            feat_dest = self._encode_feature(destination, 'Destination_Node')
            feat_mode = self._encode_feature(transport_mode, 'Transport_Mode')
            feat_leg = self._encode_feature(leg_type, 'Leg_Type')
            feat_cond = self._encode_feature(condition_flag, 'Condition_Flag')
            
            X_input = pd.DataFrame([{'Leg_Type': feat_leg, 'Origin_Node': feat_origin, 'Destination_Node': feat_dest,
                                     'Transport_Mode': feat_mode, 'Condition_Flag': feat_cond, 'NLP_Severity_Score': nlp_score}])
            
            # 1. Raw p85 Inference
            raw_prediction = float(self.model.predict(X_input)[0])
            
            # 2. Statistical Calibration (Derived from Historical p95)
            mode_key = transport_mode.lower()
            profile = self.profiles.get(mode_key, {"floor": 0.0, "cap": 240.0})
            
            floor = profile["floor"]
            cap = profile["cap"]
            
            calibrated_delay = min(max(0.0, raw_prediction), cap)
            
            # 3. Restore Systemic Friction (p5 Baseline)
            final_delay = max(calibrated_delay, floor)
            
            # Explainability
            reason = "Optimal Flow"
            if final_delay == floor and calibrated_delay < floor:
                reason = f"Baseline Operational Friction (Historical p5: {floor}h)"
            elif calibrated_delay < raw_prediction:
                reason = f"Operational Cap Applied (Historical p95 Bound: {cap}h)"
            elif raw_prediction > floor:
                reason = "Quantile Disruption Prediction (p85 Risk)"

            return {
                "raw_model_prediction": round(raw_prediction, 2),
                "calibrated_delay": round(calibrated_delay, 2),
                "baseline_systemic_friction": floor,
                "final_delay_presented": round(final_delay, 2),
                "calibration_reason": reason,
                "p_quantile": 0.85,
                "available_quantiles": ["p85"],
                "p50_delay": None,
                "p85_delay": round(final_delay, 2),
                "p95_delay": None,
                "prediction_status": "MODEL_P85",
                "is_defensible": True
            }
            
        except Exception as e:
            # Never turn a failed risk inference into an optimistic zero-delay result.
            # Use a conservative mode prior and explicitly mark the result as non-defensible.
            priors = {"road": 2.5, "sea": 48.0, "air": 12.0, "rail": 18.0}
            fallback = priors.get(transport_mode.lower(), 12.0)
            print(f"Calibration Inference Error: {e}; using conservative prior {fallback}h")
            return {
                "raw_model_prediction": None,
                "calibrated_delay": fallback,
                "baseline_systemic_friction": fallback,
                "final_delay_presented": fallback,
                "calibration_reason": f"Inference Error ({type(e).__name__}): conservative operational prior applied",
                "p_quantile": 0.85,
                "available_quantiles": ["p85"],
                "p50_delay": None,
                "p85_delay": None,
                "p95_delay": None,
                "prediction_status": "FALLBACK_INFERENCE_ERROR",
                "is_defensible": False,
            }

class ContrastiveNLPEngine:
    """Stage 2: PRODUCTION Contrastive NLP Brain."""
    def __init__(self, lazy_load=False):
        self._ready = False
        self.noise_floor = 0.04
        self.calibration_multiplier = 0.35
        if not lazy_load:
            self.warmup()

    def warmup(self):
        if self._ready: return
        print("[NLP ENGINE] Starting warmup...")
        try:
            from sentence_transformers import SentenceTransformer, util
            self.model = SentenceTransformer(
    "all-MiniLM-L6-v2",
    device="cuda" if torch.cuda.is_available() else "cpu"
)
            self.util = util
            if os.path.exists(NLP_ANCHORS_PATH):
                anchors = torch.load(NLP_ANCHORS_PATH, map_location=torch.device("cpu"))
                self.disaster_matrix = anchors["disaster_matrix"]
                self.safe_matrix = anchors["safe_matrix"]
                self._ready = True
                print(f"NLP Brain: Loaded Historical Anchor Matrix.")
            else:
                self._ready = False
        except Exception as e:
            print(f"[NLP ENGINE] Warmup failed: {e}")
            self._ready = False

    def get_semantic_score(self, news_text: str) -> float:
        # t_nlp_start = time.perf_counter()
        if not self._ready: return 0.0
        if not news_text or len(news_text.strip()) < 5: return 0.0
        chunks = [news_text[i:i+256] for i in range(0, len(news_text), 256)]
        chunk_embeddings = self.model.encode(chunks, convert_to_tensor=True)
        d_scores = self.util.cos_sim(chunk_embeddings, self.disaster_matrix)
        s_scores = self.util.cos_sim(chunk_embeddings, self.safe_matrix)
        margin = float(np.max(d_scores.cpu().numpy())) - float(np.max(s_scores.cpu().numpy()))
        # Positive margin means the text is closer to the disruption anchors.
        # The old comparison discarded precisely those high-confidence disruption signals.
        if margin <= self.noise_floor:
            return 0.0
        return float(min(1.0, max(0.0, margin * self.calibration_multiplier)))

class CARFFilter:
    """Stage 3: Context-Aware Relevance Filter for all supported transport modes."""
    def __init__(self):
        # Keep terms mode-specific and token/phrase based. In particular, ``airport``
        # must not match the sea keyword ``port`` as a substring.
        self.relevance_map = {
            "air": {"airport", "airports", "flight", "flights", "airspace", "aviation", "aircraft", "airline", "airlines", "dxb"},
            "sea": {"port", "ports", "vessel", "vessels", "ship", "ships", "canal", "canals", "ocean", "maritime", "dock", "docks", "harbor", "harbour", "container", "containers"},
            "rail": {"rail", "railway", "railways", "track", "tracks", "locomotive", "locomotives", "station", "stations", "train", "trains"},
            "road": {"highway", "highways", "truck", "trucks", "traffic", "bridge", "bridges", "road", "roads", "delivery", "trucking"},
        }

    @staticmethod
    def _tokens(text: str) -> set:
        import re
        return set(re.findall(r"\b[a-z0-9]+\b", text.lower()))

    def apply_filter(self, semantic_score: float, news_context: str, transport_mode: str) -> float:
        if semantic_score <= 0:
            return 0.0
        mode = transport_mode.lower()
        if mode not in self.relevance_map:
            return semantic_score

        tokens = self._tokens(news_context)
        own_hits = tokens & self.relevance_map[mode]
        other_hits = set().union(*(terms for m, terms in self.relevance_map.items() if m != mode)) & tokens

        # Explicitly modal news that names another transport mode is irrelevant.
        # If it names this mode, retain the semantic threat score. If it has no
        # explicit modal cue, leave the semantic model's signal untouched.
        if other_hits and not own_hits:
            return 0.0
        return float(semantic_score)

    def max_pool_threats(self, scores: List[float]) -> float:
        return float(np.max(scores)) if scores else 0.0
