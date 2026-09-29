from backend.engine.threat_intelligence import CARFFilter


def test_carf_preserves_relevant_modal_signals():
    carf = CARFFilter()
    assert carf.apply_filter(0.8, "Major port strike closed container terminals.", "sea") == 0.8
    assert carf.apply_filter(0.8, "International airport cargo handling is suspended.", "air") == 0.8
    assert carf.apply_filter(0.8, "Rail freight workers strike at the station.", "rail") == 0.8
    assert carf.apply_filter(0.8, "Highway bridge collapse halts truck traffic.", "road") == 0.8


def test_carf_rejects_explicitly_other_modal_signals():
    carf = CARFFilter()
    assert carf.apply_filter(0.8, "Airport strike cancelled international flights.", "sea") == 0.0
    assert carf.apply_filter(0.8, "Port strike closed container terminals.", "air") == 0.0
    assert carf.apply_filter(0.8, "Airport strike cancelled flights.", "rail") == 0.0
    assert carf.apply_filter(0.8, "Port strike closed terminals.", "road") == 0.0


def test_carf_does_not_match_airport_as_port():
    carf = CARFFilter()
    assert carf.apply_filter(0.8, "Airport strike cancelled flights.", "sea") == 0.0
    assert carf.apply_filter(0.8, "Airport strike cancelled flights.", "air") == 0.8


def test_carf_preserves_semantic_signal_when_no_modal_cue_exists():
    carf = CARFFilter()
    assert carf.apply_filter(0.8, "Major earthquake has damaged infrastructure.", "sea") == 0.8
