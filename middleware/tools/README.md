# ARC Conversion Tools

A collection of utilities for converting between ARC (Annotated Research Context) and RO-Crate JSON formats.

## Overview

This package provides command-line tools to:

- Convert ARC files to RO-Crate JSON format
- Convert RO-Crate JSON files back to ARC format

These tools are useful for testing, debugging, and data interchange between ARC-based workflows and RO-Crate consumers.

## Installation

```bash
pip install -e .
```

Or using uv:

```bash
uv pip install -e .
```

## Tools

### arc2rocrate.py

Converts an ARC file to RO-Crate JSON format.

**Usage:**

```bash
python arc2rocrate.py <input.arc> <output.json>
```

**Example:**

```bash
python arc2rocrate.py my_research.arc my_research_rocrate.json
```

**Features:**

- Loads ARC from file
- Exports as RO-Crate JSON string
- Measures and reports conversion time
- Writes JSON to output file

### rocrate2arc.py

Converts a RO-Crate JSON file to ARC format.

**Usage:**

```bash
python rocrate2arc.py <input.json> <output.arc>
```

**Example:**

```bash
python rocrate2arc.py my_research_rocrate.json restored_research.arc
```

**Features:**

- Reads RO-Crate JSON from file
- Converts to ARC format
- Includes profiling for performance analysis
- Generates performance statistics (`profile.stats`)

## Performance Profiling

The `rocrate2arc.py` tool includes built-in profiling that generates detailed performance statistics. After running the conversion, check the `profile.stats` file and the console output for the top 20 most time-consuming operations.

## Dependencies

- `arctrl>=3.0.0b15` - ARC and RO-Crate conversion library

## Requirements

- Python >= 3.12

## Development

This package is part of the FAIRagro Advanced Middleware project and is used for testing and development of ARC conversion workflows.

## License

See the main project LICENSE file.
