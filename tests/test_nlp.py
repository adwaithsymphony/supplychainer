import types
import numpy as np
from backend.engine.threat_intelligence import ContrastiveNLPEngine


class _T:
    def __init__(self, a): self.a = np.asarray(a, float)
    def cpu(self): return self
    def numpy(self): return self.a


def _cos(a, b):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    return _T((a / np.linalg.norm(a, axis=1, keepdims=True)) @ (b / np.linalg.norm(b, axis=1, keepdims=True)).T)


class _Model:
    def encode(self, chunks, convert_to_tensor=True):
        rows = []
        for ch in chunks:
            l = ch.lower()
            if "strike" in l or "closed" in l:
                rows.append([1.0, 0.1])
            elif "normal" in l or "routine" in l:
                rows.append([0.1, 1.0])
            else:
                rows.append([0.7, 0.7])
        return np.array(rows)


def make_mock_nlp():
    n = ContrastiveNLPEngine(lazy_load=True)
    n._ready = True
    n.model = _Model()
    n.util = types.SimpleNamespace(cos_sim=_cos)
    n.disaster_matrix = np.array([[1.0, 0.0]])
    n.safe_matrix = np.array([[0.0, 1.0]])
    return n


def test_positive_disaster_margin_is_not_discarded():
    n = make_mock_nlp()
    score = n.get_semantic_score("Major port strike has closed terminals.")
    assert score > 0
    assert score <= 1


def test_safe_text_has_zero_threat():
    n = make_mock_nlp()
    assert n.get_semantic_score("Routine normal operations, all on time.") == 0.0


def test_neutral_text_has_zero_threat():
    n = make_mock_nlp()
    assert n.get_semantic_score("Weekly shipping bulletin published today.") == 0.0
