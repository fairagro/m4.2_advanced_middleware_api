# ARC Store — Delta

## ADDED Requirements

### Requirement: Use shallow clones for Git CLI working copies

When the Git CLI backends create a fresh local working copy by cloning a remote,
the clone MUST be shallow with depth 1. The tip working tree MUST still contain
the files needed for catalog finalize and per-ARC sync or get. Tip content after
clone, commit, and push MUST match what a full-history clone would produce for
the same tip-only operations. Empty or missing remotes that fall back to local
repository initialization are unchanged. Operators MUST NOT need a configuration
knob to enable this depth.

#### Scenario: Fresh clone is shallow

- **GIVEN** a Git CLI backend operation that clones into a new local working directory
- **WHEN** the clone completes successfully
- **THEN** the local repository history depth is 1
- **AND** the tip working tree is usable for the operation (read/write tip files,
  commit, and push as applicable)

#### Scenario: Catalog publish result unchanged vs tip-only needs

- **GIVEN** a consolidated catalog remote whose tip already contains `{rdi}.json`
- **WHEN** catalog finalize publishes identical bytes for that RDI
- **THEN** the store skips commit/push as today
- **AND** when bytes differ, the pushed tip file matches the serialized catalog
  bytes
