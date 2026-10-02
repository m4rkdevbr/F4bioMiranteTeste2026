"""Public package exports."""

__version__ = "1.0.0"


def build_graph():
    from modernization_pipeline.graph import build_graph as _build_graph

    return _build_graph()


def get_compiled_graph():
    from modernization_pipeline.graph import get_compiled_graph as _get

    return _get()


__all__ = ["build_graph", "get_compiled_graph", "__version__"]
