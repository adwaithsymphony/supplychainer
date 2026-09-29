from backend.engine.threat_intelligence import ThreatIntelligencePredictor


def test_real_p85_artifact_produces_defensible_prediction():
    p = ThreatIntelligencePredictor(lazy_load=True)
    p.warmup()
    assert p.is_trained
    result = p.predict_worst_case_delay("Seattle", "Shanghai", "sea", condition_flag="Disrupted", nlp_score=0.9)
    assert result["p_quantile"] == 0.85
    assert result["final_delay_presented"] > 0
    assert result["is_defensible"] is True


def test_prediction_failure_is_not_silent_zero():
    p = ThreatIntelligencePredictor(lazy_load=True)
    p.warmup()
    p.model.predict = lambda _X: (_ for _ in ()).throw(RuntimeError("boom"))
    result = p.predict_worst_case_delay("Seattle", "Shanghai", "sea")
    assert result["final_delay_presented"] > 0
    assert result["is_defensible"] is False
    assert "Inference Error" in result["calibration_reason"]
