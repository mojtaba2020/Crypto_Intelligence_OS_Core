import importlib.util
from pathlib import Path


def _load_script(name: str):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    import sys

    sys.path.insert(0, str(scripts))
    try:
        path = scripts / f"{name}.py"
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def test_transitive_dependents_finds_downstream_chain() -> None:
    module = _load_script("impact_report")
    graph = {
        "pkg.a": [],
        "pkg.b": ["pkg.a"],
        "pkg.c": ["pkg.b"],
        "pkg.unrelated": [],
    }
    assert module.transitive_dependents(graph, {"pkg.a"}) == {"pkg.a", "pkg.b", "pkg.c"}


def test_contract_change_is_multi_module() -> None:
    module = _load_script("impact_report")
    files = ["src/crypto_intelligence_os/contracts/base.py"]
    assert module.impact_level(files) == "MULTI_MODULE"
