"""JSON value types for wire-format documents (RO-Crate, CouchDB, catalog files)."""

from __future__ import annotations

type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | list[JsonValue] | dict[str, JsonValue]

type JsonObject = dict[str, JsonValue]
type RoCrateContent = JsonObject
type RoCrateGraphNode = JsonObject
type CatalogDatasetRecord = JsonObject
type CouchDbDocument = JsonObject
