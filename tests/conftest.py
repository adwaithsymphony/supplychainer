import os
import sys
import types

# Tests are deterministic and offline. The production dependency is still listed in
# requirements; this fallback only lets the suite run when feedparser is absent.
try:
    import feedparser  # noqa: F401
except ImportError:
    stub = types.ModuleType("feedparser")
    stub.parse = lambda _url: types.SimpleNamespace(entries=[])
    sys.modules["feedparser"] = stub

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
