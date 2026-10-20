"""Unit tests for Celery task payload models."""

import json

from middleware.api.business_logic.task_payloads import ArcSyncTask


def test_arc_sync_task_round_trip_includes_change_flags() -> None:
    """ArcSyncTask JSON dump/load preserves is_new / has_changes for Celery."""
    task = ArcSyncTask(
        rdi="rdi-1",
        arc=json.dumps({"@graph": []}),
        client_id="client",
        is_new=False,
        has_changes=False,
    )
    restored = ArcSyncTask.model_validate(json.loads(task.model_dump_json()))
    assert restored.is_new is False
    assert restored.has_changes is False
    assert restored.rdi == "rdi-1"


def test_arc_sync_task_defaults_flags_for_legacy_payloads() -> None:
    """Old queue messages without flags default to full-sync (is_new/has_changes True)."""
    restored = ArcSyncTask.model_validate({"rdi": "rdi-1", "arc": "{}", "client_id": None})
    assert restored.is_new is True
    assert restored.has_changes is True
