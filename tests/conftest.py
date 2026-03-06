"""
Session-wide fixtures and mocks.

Streamlit must be patched in sys.modules BEFORE any project module is imported,
otherwise `import streamlit as st` in app.py executes real Streamlit calls
(set_page_config, title, etc.) that error out in a headless test environment.
"""
import sys
from unittest.mock import MagicMock

# ─────────────────────────────────────────────────────────────────────────────
# Build a minimal Streamlit mock.
# ─────────────────────────────────────────────────────────────────────────────
_st = MagicMock()

# @st.cache_data(ttl=60) is a two-level decorator; make it a passthrough so
# load_data() behaves as a plain function in tests (no caching side-effects).
_st.cache_data = lambda ttl=None: (lambda f: f)

# Context managers used at module level in app.py (with st.expander / st.spinner).
for _attr in ("expander", "spinner"):
    _cm = MagicMock()
    _cm.__enter__ = MagicMock(return_value=_cm)
    _cm.__exit__ = MagicMock(return_value=False)
    setattr(_st, _attr, MagicMock(return_value=_cm))

# app.py uses sidebar widget return values as dict keys (e.g. PROVIDER_DEFAULTS[selected_provider]).
# Return sensible defaults so module-level execution on import doesn't raise KeyError.
# st.columns(n) must unpack into n items.
_st.columns = lambda n: [MagicMock() for _ in range(n if isinstance(n, int) else len(n))]

_st.sidebar.selectbox.return_value = "Gemini"   # valid PROVIDER_DEFAULTS key
_st.sidebar.slider.return_value = 3.0            # numeric sensitivity value
_st.sidebar.text_input.return_value = "gemini-2.5-flash"

sys.modules["streamlit"] = _st
