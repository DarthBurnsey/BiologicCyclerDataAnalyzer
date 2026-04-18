from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from legacy_import_bootstrap import prefer_legacy_modules


def test_prefer_legacy_modules_moves_repo_root_first_and_evicts_backend_shadow(monkeypatch):
    repo_root = Path("/tmp/cellscope-root")
    backend_root = repo_root / "Cellscope 2.0" / "backend"
    backend_database = backend_root / "database.py"

    monkeypatch.setattr(sys, "path", ["/other/location", str(backend_root), str(repo_root)])
    monkeypatch.setitem(
        sys.modules,
        "database",
        SimpleNamespace(__file__=str(backend_database)),
    )

    prefer_legacy_modules(
        repo_root=repo_root,
        backend_root=backend_root,
        module_names=("database", "data_processing"),
    )

    assert sys.path[0] == str(repo_root.resolve())
    assert "database" not in sys.modules


def test_prefer_legacy_modules_keeps_non_backend_module_loaded(monkeypatch):
    repo_root = Path("/tmp/cellscope-root")
    backend_root = repo_root / "Cellscope 2.0" / "backend"
    legacy_database = repo_root / "database.py"

    monkeypatch.setattr(sys, "path", [str(repo_root), "/other/location"])
    monkeypatch.setitem(
        sys.modules,
        "database",
        SimpleNamespace(__file__=str(legacy_database)),
    )

    prefer_legacy_modules(
        repo_root=repo_root,
        backend_root=backend_root,
        module_names=("database",),
    )

    assert sys.modules["database"].__file__ == str(legacy_database)
