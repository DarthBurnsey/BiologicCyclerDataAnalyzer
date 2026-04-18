"""Lightweight Streamlit stub for root-level tests."""

from __future__ import annotations

import functools
import types


class MockSessionState:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def __setitem__(self, key, value):
        self.data[key] = value

    def __getitem__(self, key):
        return self.data[key]

    def __contains__(self, key):
        return key in self.data

    def pop(self, key, default=None):
        return self.data.pop(key, default)

    def clear(self):
        self.data.clear()


def _no_op_cache_data(*decorator_args, **decorator_kwargs):
    """Mimic st.cache_data as a no-op decorator in tests."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    if decorator_args and callable(decorator_args[0]) and len(decorator_args) == 1 and not decorator_kwargs:
        return decorator_args[0]

    return decorator


def install_streamlit_stub():
    """Install a minimal streamlit module for tests that import UI helpers."""
    st = types.ModuleType("streamlit")
    st.session_state = MockSessionState()
    st.cache_data = _no_op_cache_data
    st.cache_resource = _no_op_cache_data
    st.stop = lambda: None
    st.rerun = lambda: None
    st.warning = lambda *args, **kwargs: None
    st.info = lambda *args, **kwargs: None
    st.error = lambda *args, **kwargs: None
    st.caption = lambda *args, **kwargs: None
    st.markdown = lambda *args, **kwargs: None
    st.dataframe = lambda *args, **kwargs: None
    st.text_area = lambda *args, **kwargs: None
    st.download_button = lambda *args, **kwargs: False
    st.button = lambda *args, **kwargs: False
    st.checkbox = lambda *args, **kwargs: False
    st.selectbox = lambda *args, **kwargs: None
    st.multiselect = lambda *args, **kwargs: []
    st.slider = lambda *args, **kwargs: kwargs.get("value")
    st.columns = lambda *args, **kwargs: []
    st.container = lambda *args, **kwargs: types.SimpleNamespace(__enter__=lambda self: self, __exit__=lambda *args: None)
    st.expander = lambda *args, **kwargs: st.container()
    st.header = lambda *args, **kwargs: None
    st.subheader = lambda *args, **kwargs: None
    st.radio = lambda *args, **kwargs: None
    st.metric = lambda *args, **kwargs: None
    return st
