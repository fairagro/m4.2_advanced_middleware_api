"""Data models for the SQL-to-ARC conversion process."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class ArcBuildData(BaseModel):
    """Data bundle for building a single ARC."""

    investigation_row: dict[str, Any]
    studies: list[dict[str, Any]]
    assays: list[dict[str, Any]]
    contacts: list[dict[str, Any]]
    publications: list[dict[str, Any]]
    annotations: list[dict[str, Any]]

    model_config = ConfigDict(arbitrary_types_allowed=True)


class WorkerContext(BaseModel):
    """Context data for a worker process."""

    client: Any  # ApiClient, but Any to allow mocking
    rdi: str
    studies_by_inv: dict[str, list[dict[str, Any]]]
    assays_by_inv: dict[str, list[dict[str, Any]]]
    contacts_by_inv: dict[str, list[dict[str, Any]]]
    pubs_by_inv: dict[str, list[dict[str, Any]]]
    anns_by_inv: dict[str, list[dict[str, Any]]]
    worker_id: int
    total_workers: int
    executor: Any  # ProcessPoolExecutor is not Pydantic-friendly easily, so Any

    model_config = ConfigDict(arbitrary_types_allowed=True)
