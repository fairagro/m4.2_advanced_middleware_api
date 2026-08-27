"""Pinned ARC / Bioschemas short names for catalog JSON-LD compact."""

from __future__ import annotations

# Observed ARC RO-Crate extension fragment (Lab / Sample / ISA table terms).
ARC_BIOSCHEMAS_EXTENSION_CONTEXT: dict[str, str] = {
    "LabProcess": "https://bioschemas.org/LabProcess",
    "LabProtocol": "https://bioschemas.org/LabProtocol",
    "Sample": "https://bioschemas.org/Sample",
    "columnIndex": "https://w3id.org/ro/terms/arc#columnIndex",
    "computationalTool": "https://bioschemas.org/properties/computationalTool",
    "executesLabProtocol": "https://bioschemas.org/properties/executesLabProtocol",
    "intendedUse": "https://bioschemas.org/properties/intendedUse",
    "labEquipment": "https://bioschemas.org/properties/labEquipment",
    "parameterValue": "https://bioschemas.org/properties/parameterValue",
    "reagent": "https://bioschemas.org/properties/reagent",
}
