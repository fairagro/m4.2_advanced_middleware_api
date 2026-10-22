"""Tests for LocalOfflineConfig startup gates."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from middleware.api_local_offline.config import LocalOfflineConfig


def test_from_data_accepts_output_root(tmp_path: Path) -> None:
    cfg = LocalOfflineConfig.from_data({"output_root": str(tmp_path)})
    assert cfg.output_root == tmp_path


def test_from_data_rejects_couchdb_key() -> None:
    with pytest.raises(ValueError, match="refuses production config keys"):
        LocalOfflineConfig.from_data({"output_root": "/data/arcs", "couchdb": {"url": "http://x"}})


def test_from_data_rejects_celery_and_arc_store_keys() -> None:
    with pytest.raises(ValueError, match="celery"):
        LocalOfflineConfig.from_data({
            "output_root": "/data/arcs",
            "celery": {"broker_url": "amqp://x"},
            "arc_store": {"git_repo": {}},
        })


def test_from_yaml_file_rejects_production_keys(tmp_path: Path) -> None:
    path = tmp_path / "mixed.yaml"
    path.write_text(
        "output_root: /data/arcs\ncouchdb:\n  url: http://x\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="refuses production config keys"):
        LocalOfflineConfig.from_yaml_file(path)


def test_extra_forbid_rejects_unknown_key() -> None:
    with pytest.raises(ValidationError):
        LocalOfflineConfig.model_validate({"output_root": "/data/arcs", "not_a_setting": 1})
