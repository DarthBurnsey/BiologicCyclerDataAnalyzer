"""Helpers for keeping legacy app imports bound to the repo-root modules."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable


def _move_path_to_front(path: Path) -> None:
    normalized = str(path.resolve())
    sys.path[:] = [normalized] + [
        entry for entry in sys.path
        if entry != normalized
    ]


def prefer_legacy_modules(
    *,
    repo_root: Path,
    module_names: Iterable[str],
    backend_root: Path | None = None,
) -> None:
    resolved_repo_root = Path(repo_root).resolve()
    resolved_backend_root = (
        Path(backend_root).resolve()
        if backend_root is not None
        else resolved_repo_root / "Cellscope 2.0" / "backend"
    )

    _move_path_to_front(resolved_repo_root)

    for module_name in module_names:
        loaded_module = sys.modules.get(module_name)
        loaded_path = getattr(loaded_module, "__file__", None)
        if not loaded_path:
            continue

        try:
            resolved_module_path = Path(loaded_path).resolve()
        except Exception:
            continue

        if resolved_module_path == resolved_backend_root / f"{module_name}.py" or resolved_backend_root in resolved_module_path.parents:
            sys.modules.pop(module_name, None)
