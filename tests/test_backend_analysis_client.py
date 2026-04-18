from __future__ import annotations

import sys
import types

import backend_analysis_client as client


def test_list_study_workspace_records_prefers_backend_service(monkeypatch):
    backend_called = {"count": 0}

    def backend_list():
        backend_called["count"] += 1
        return [{"id": 1, "name": "Backend Workspace"}]

    def backend_get(workspace_id: int, *, refresh: bool = False):
        return {"summary": {"workspace_id": workspace_id, "refresh": refresh}}

    def backend_list_snapshots():
        return []

    def backend_get_snapshot(snapshot_id: int):
        return {"id": snapshot_id}

    monkeypatch.setattr(
        client,
        "_load_backend_analysis_services",
        lambda: (backend_list, backend_get, backend_list_snapshots, backend_get_snapshot),
    )

    records = client.list_study_workspace_records()

    assert backend_called["count"] == 1
    assert records == [{"id": 1, "name": "Backend Workspace"}]


def test_get_study_workspace_payload_preferred_uses_backend_when_not_refreshing(monkeypatch):
    backend_calls = {"count": 0}

    def backend_list():
        return []

    def backend_get(workspace_id: int, *, refresh: bool = False):
        backend_calls["count"] += 1
        return {"summary": {"workspace_id": workspace_id, "source": "backend", "refresh": refresh}}

    def backend_list_snapshots():
        return []

    def backend_get_snapshot(snapshot_id: int):
        return {"id": snapshot_id}

    monkeypatch.setattr(
        client,
        "_load_backend_analysis_services",
        lambda: (backend_list, backend_get, backend_list_snapshots, backend_get_snapshot),
    )

    payload = client.get_study_workspace_payload_preferred(7, refresh=False)

    assert backend_calls["count"] == 1
    assert payload == {"summary": {"workspace_id": 7, "source": "backend", "refresh": False}}


def test_get_study_workspace_payload_preferred_falls_back_to_legacy_on_refresh(monkeypatch):
    def backend_list():
        return []

    def backend_get(workspace_id: int, *, refresh: bool = False):
        raise AssertionError("backend read path should not be used for explicit refresh")

    def backend_list_snapshots():
        return []

    def backend_get_snapshot(snapshot_id: int):
        return {"id": snapshot_id}

    monkeypatch.setattr(
        client,
        "_load_backend_analysis_services",
        lambda: (backend_list, backend_get, backend_list_snapshots, backend_get_snapshot),
    )

    import study_workspace_service

    monkeypatch.setattr(
        study_workspace_service,
        "build_study_workspace_payload",
        lambda workspace_id, *, refresh=False, compute_missing_legacy=True: {
            "summary": {
                "workspace_id": workspace_id,
                "source": "legacy",
                "refresh": refresh,
                "compute_missing_legacy": compute_missing_legacy,
            }
        },
    )

    payload = client.get_study_workspace_payload_preferred(9, refresh=True)

    assert payload == {
        "summary": {
            "workspace_id": 9,
            "source": "legacy",
            "refresh": True,
            "compute_missing_legacy": True,
        }
    }


def test_get_study_workspace_payload_preferred_falls_back_when_backend_fails(monkeypatch):
    monkeypatch.setattr(
        client,
        "_load_backend_analysis_services",
        lambda: (_ for _ in ()).throw(RuntimeError("backend unavailable")),
    )

    import study_workspace_service

    monkeypatch.setattr(
        study_workspace_service,
        "build_study_workspace_payload",
        lambda workspace_id, *, refresh=False, compute_missing_legacy=True: {
            "summary": {
                "workspace_id": workspace_id,
                "source": "legacy",
                "refresh": refresh,
            }
        },
    )

    payload = client.get_study_workspace_payload_preferred(5, refresh=False)

    assert payload == {
        "summary": {
            "workspace_id": 5,
            "source": "legacy",
            "refresh": False,
        }
    }


def test_list_cohort_snapshot_records_prefers_backend_service(monkeypatch):
    backend_called = {"count": 0}

    def backend_list():
        return []

    def backend_get(workspace_id: int, *, refresh: bool = False):
        return {"summary": {"workspace_id": workspace_id, "refresh": refresh}}

    def backend_list_snapshots():
        backend_called["count"] += 1
        return [{"id": 3, "name": "Backend Snapshot"}]

    def backend_get_snapshot(snapshot_id: int):
        return {"id": snapshot_id}

    monkeypatch.setattr(
        client,
        "_load_backend_analysis_services",
        lambda: (backend_list, backend_get, backend_list_snapshots, backend_get_snapshot),
    )

    records = client.list_cohort_snapshot_records()

    assert backend_called["count"] == 1
    assert records == [{"id": 3, "name": "Backend Snapshot"}]


def test_get_cohort_snapshot_payload_preferred_uses_backend_and_falls_back(monkeypatch):
    def backend_list():
        return []

    def backend_get(workspace_id: int, *, refresh: bool = False):
        return None

    def backend_list_snapshots():
        return []

    def backend_get_snapshot(snapshot_id: int):
        return {"id": snapshot_id, "name": "Backend Snapshot"}

    monkeypatch.setattr(
        client,
        "_load_backend_analysis_services",
        lambda: (backend_list, backend_get, backend_list_snapshots, backend_get_snapshot),
    )

    payload = client.get_cohort_snapshot_payload_preferred(12)
    assert payload == {"id": 12, "name": "Backend Snapshot"}

    monkeypatch.setattr(
        client,
        "_load_backend_analysis_services",
        lambda: (_ for _ in ()).throw(RuntimeError("backend unavailable")),
    )

    import cohort_tools

    monkeypatch.setattr(
        cohort_tools,
        "get_cohort_snapshot",
        lambda snapshot_id: {"id": snapshot_id, "name": "Legacy Snapshot"},
    )

    fallback_payload = client.get_cohort_snapshot_payload_preferred(13)
    assert fallback_payload == {"id": 13, "name": "Legacy Snapshot"}


def test_load_backend_analysis_services_does_not_leave_backend_root_first_on_sys_path(monkeypatch):
    backend_path = str(client.BACKEND_ROOT)
    original_path = ["repo-root", "site-packages"]
    monkeypatch.setattr(sys, "path", list(original_path))

    fake_module = types.SimpleNamespace(
        list_study_workspace_payloads=lambda: [],
        get_study_workspace_payload=lambda workspace_id, *, refresh=False: None,
        list_cohort_snapshot_payloads=lambda: [],
        get_cohort_snapshot_payload=lambda snapshot_id: None,
    )

    def fake_import_module(name: str):
        assert name == "app.services.workspaces"
        assert sys.path[0] == backend_path
        sys.path.insert(0, "repo-restored-by-backend")
        return fake_module

    monkeypatch.setattr(client.importlib, "import_module", fake_import_module)

    services = client._load_backend_analysis_services()

    assert services == (
        fake_module.list_study_workspace_payloads,
        fake_module.get_study_workspace_payload,
        fake_module.list_cohort_snapshot_payloads,
        fake_module.get_cohort_snapshot_payload,
    )
    assert sys.path[0] == "repo-restored-by-backend"
    assert backend_path not in sys.path
