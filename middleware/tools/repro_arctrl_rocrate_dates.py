#!/usr/bin/env python3
"""Minimal reproducer: ISA dates lost on RO-Crate -> ARC -> RO-Crate round-trip.

Run:
    uv run --with "arctrl>=3.0.5" python repro_arctrl_rocrate_dates.py

Profile: https://github.com/nfdi4plants/isa-ro-crate-profile/blob/main/profile/isa_ro_crate.md
  Submission Date      -> dateCreated
  Public Release Date  -> datePublished
"""

from __future__ import annotations

import importlib.metadata
import json

from arctrl import ARC  # type: ignore[import-untyped]

# ro_crates/minimal.json (embedded so this file is self-contained)
MINIMAL_ROCRATE = {
    "@context": "https://w3id.org/ro/crate/1.2/context",
    "@graph": [
        {
            "@id": "./",
            "@type": "Dataset",
            "additionalType": "Investigation",
            "identifier": "Test",
        },
        {
            "@id": "ro-crate-metadata.json",
            "@type": "CreativeWork",
            "conformsTo": {"@id": "https://w3id.org/ro/crate/1.2"},
            "about": {"@id": "./"},
        },
    ],
}

SUBMISSION_DATE = "2024-01-15"
PUBLIC_RELEASE_DATE = "2025-06-01"

input_json = json.dumps(MINIMAL_ROCRATE)
arc = ARC.from_rocrate_json_string(input_json)
arc.Title = "Test"
arc.SubmissionDate = SUBMISSION_DATE
arc.PublicReleaseDate = PUBLIC_RELEASE_DATE

output_json = arc.ToROCrateJsonString()
root = next(node for node in json.loads(output_json)["@graph"] if node.get("@id") == "./")

print(f"arctrl {importlib.metadata.version('arctrl')}\n")
print("1) Input RO-Crate (minimal.json, no dates):")
print(json.dumps(MINIMAL_ROCRATE, indent=2))
print("\n2) After from_rocrate_json_string, set on ARC object:")
print(f"  Title               = {arc.Title!r}")
print(f"  SubmissionDate      = {arc.SubmissionDate!r}")
print(f"  PublicReleaseDate   = {arc.PublicReleaseDate!r}")
print("\n3) Output RO-Crate root after ToROCrateJsonString():")
print(f"  dateCreated         = {root.get('dateCreated')!r}")
print(f"  datePublished       = {root.get('datePublished')!r}")
print(f"  sdDatePublished     = {root.get('sdDatePublished')!r}")
print("\nISA date strings present anywhere in output JSON?")
print(f"  {SUBMISSION_DATE!r} in output: {SUBMISSION_DATE in output_json}")
print(f"  {PUBLIC_RELEASE_DATE!r} in output: {PUBLIC_RELEASE_DATE in output_json}")
print("\n4) Full output RO-Crate JSON:")
print(json.dumps(json.loads(output_json), indent=2))
